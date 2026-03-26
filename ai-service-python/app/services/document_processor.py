import io

import structlog

from app.core.exceptions import DocumentProcessingError

logger = structlog.get_logger()


class DocumentProcessor:
    """Extracts plain text from various document formats."""

    SUPPORTED_TYPES = {"pdf", "docx", "xlsx", "pptx", "txt", "md"}

    def extract_text(self, content: bytes, file_type: str) -> str:
        file_type = file_type.lower().strip(".")
        if file_type not in self.SUPPORTED_TYPES:
            raise DocumentProcessingError(f"Unsupported file type: {file_type}")

        try:
            extractor = getattr(self, f"_extract_{file_type}")
            text = extractor(content)
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error("Text extraction failed", file_type=file_type, error=str(e))
            raise DocumentProcessingError(
                f"Failed to extract text from {file_type}: {e}"
            ) from e

        text = text.strip()
        if not text:
            raise DocumentProcessingError("Extracted text is empty")

        logger.info("Text extracted", file_type=file_type, char_count=len(text))
        return text

    def _extract_pdf(self, content: bytes) -> str:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    def _extract_docx(self, content: bytes) -> str:
        from docx import Document

        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    def _extract_xlsx(self, content: bytes) -> str:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheets = []
        for sheet in wb.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(cell) for cell in row if cell is not None]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                sheets.append(f"[{sheet.title}]\n" + "\n".join(rows))
        wb.close()
        return "\n\n".join(sheets)

    def _extract_pptx(self, content: bytes) -> str:
        from pptx import Presentation

        prs = Presentation(io.BytesIO(content))
        slides = []
        for i, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            texts.append(text)
            if texts:
                slides.append(f"[Slide {i}]\n" + "\n".join(texts))
        return "\n\n".join(slides)

    def _extract_txt(self, content: bytes) -> str:
        return content.decode("utf-8", errors="replace")

    def _extract_md(self, content: bytes) -> str:
        return content.decode("utf-8", errors="replace")
