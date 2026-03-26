import pytest

from app.core.exceptions import DocumentProcessingError
from app.services.document_processor import DocumentProcessor


class TestDocumentProcessor:
    def setup_method(self):
        self.processor = DocumentProcessor()

    def test_extract_txt(self):
        content = b"Hello, this is a test document."
        text = self.processor.extract_text(content, "txt")
        assert text == "Hello, this is a test document."

    def test_extract_md(self):
        content = b"# Heading\n\nSome markdown content."
        text = self.processor.extract_text(content, "md")
        assert "Heading" in text
        assert "markdown content" in text

    def test_extract_txt_unicode(self):
        content = "Conformité réglementaire pharmaceutique".encode("utf-8")
        text = self.processor.extract_text(content, "txt")
        assert "Conformité" in text
        assert "pharmaceutique" in text

    def test_unsupported_file_type(self):
        with pytest.raises(DocumentProcessingError, match="Unsupported file type"):
            self.processor.extract_text(b"content", "xyz")

    def test_empty_content(self):
        with pytest.raises(DocumentProcessingError, match="empty"):
            self.processor.extract_text(b"", "txt")

    def test_whitespace_only_content(self):
        with pytest.raises(DocumentProcessingError, match="empty"):
            self.processor.extract_text(b"   \n\n   ", "txt")

    def test_file_type_normalization(self):
        content = b"Test content"
        # Should handle dot prefix and case
        text = self.processor.extract_text(content, ".TXT")
        assert text == "Test content"

    def test_supported_types(self):
        assert DocumentProcessor.SUPPORTED_TYPES == {"pdf", "docx", "xlsx", "pptx", "txt", "md"}
