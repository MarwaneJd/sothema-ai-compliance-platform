"""Token-aware text chunking.

Two chunkers are exposed:

  - TextChunker: simple sentence+paragraph splitter, suitable for
    unstructured text (emails, free-form notes).
  - RegulatoryChunker: hierarchy-aware splitter for SOPs and regulatory
    documents. Detects numbered sections (`4.2.1 …`), `Article N`,
    `Chapitre N`, all-caps headings; never splits across `Article`
    boundaries unless an article exceeds 2× chunk_size; emits a
    section-path breadcrumb that can be prepended to the chunk text
    before embedding/BM25 indexing.

The breadcrumb is intentionally NOT persisted on the TextSegment row —
the SQL Server table is shared with .NET EF Core, so adding columns
requires a coordinated migration. Callers prepend the breadcrumb at
index time only; the raw `content` is what goes into the DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pysbd
import tiktoken


@dataclass
class TextChunk:
    content: str
    chunk_index: int
    token_count: int
    breadcrumb: str = ""  # e.g. "Document › Chapitre 4 › 4.2.1 Contrôle"

    def for_indexing(self) -> str:
        """Text to embed and to push into BM25 — breadcrumb prepended so
        section context is searchable. Use for retrieval, not for display."""
        if not self.breadcrumb:
            return self.content
        return f"{self.breadcrumb}\n\n{self.content}"


# --- Heading detection (regulatory documents) -----------------------------

# Numbered sections like "4", "4.2", "4.2.1" followed by a title that starts
# with an upper-case letter. Allow accented French capitals.
_NUMBERED_HEADING_RE = re.compile(
    r"^\s*(\d+(?:\.\d+){0,4})\s+([A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ][^\n]{0,200})\s*$"
)

# "Article 4", "Article 4.2", "ARTICLE 4 - Title", etc.
# Separator class includes hyphen, en-dash, em-dash, and colon.
_ARTICLE_HEADING_RE = re.compile(
    r"^\s*(Article|ARTICLE)\s+(\d+(?:\.\d+)?)\s*[-–—:]?\s*([^\n]{0,200})\s*$"
)

# "Chapitre 1", "CHAPITRE I - …", roman or arabic numerals
_CHAPTER_HEADING_RE = re.compile(
    r"^\s*(Chapitre|CHAPITRE|Chapter|CHAPTER)\s+([IVX\d]+)\s*[-–—:]?\s*([^\n]{0,200})\s*$"
)


def _strip_title_leader(title: str) -> str:
    """Drop any residual leading dash/colon characters left after heading
    detection — keeps breadcrumbs from rendering with doubled separators."""
    return title.lstrip("-–—: \t")

# All-caps line of 3+ words, used as section title.
_ALLCAPS_HEADING_RE = re.compile(
    r"^\s*([A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ][A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ\s\-/']{6,200})\s*$"
)


@dataclass
class _Heading:
    level: int        # 0 = chapter, 1 = article, 2..N = numbered depth
    label: str        # the rendered heading, used in the breadcrumb
    line_no: int      # 0-based line index where the heading appears


def _detect_heading(line: str) -> _Heading | None:
    """Classify a single line as a heading (or None)."""
    m = _CHAPTER_HEADING_RE.match(line)
    if m:
        title = _strip_title_leader(m.group(3).strip())
        label = f"{m.group(1).title()} {m.group(2)}"
        if title:
            label = f"{label} — {title}"
        return _Heading(level=0, label=label, line_no=-1)

    m = _ARTICLE_HEADING_RE.match(line)
    if m:
        title = _strip_title_leader(m.group(3).strip())
        label = f"Article {m.group(2)}"
        if title:
            label = f"{label} — {title}"
        return _Heading(level=1, label=label, line_no=-1)

    m = _NUMBERED_HEADING_RE.match(line)
    if m:
        number = m.group(1)
        title = m.group(2).strip()
        depth = number.count(".") + 2  # "4" → 2, "4.2" → 3, "4.2.1" → 4
        return _Heading(level=depth, label=f"{number} {title}", line_no=-1)

    m = _ALLCAPS_HEADING_RE.match(line)
    if m and len(line.split()) >= 3:
        return _Heading(level=2, label=line.strip(), line_no=-1)

    return None


@dataclass
class _Section:
    """A contiguous block of text under a single (sub)heading."""
    breadcrumb: str
    text: str
    boundary_strength: int = 0  # 0 = ordinary, 1 = article boundary (don't cross)
    extra: dict = field(default_factory=dict)


# --- Chunkers --------------------------------------------------------------


class TextChunker:
    """Simple token-aware text chunking using tiktoken.

    Kept as the fallback chunker for unstructured text. RegulatoryChunker
    is preferred for SOPs / regulatory documents.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        # Use pysbd for sentence detection — handles French abbreviations
        # (Art., n°, M., decimals) far better than a regex split on `[.!?]`.
        self._sbd = pysbd.Segmenter(language="fr", clean=False)

    def chunk_text(self, text: str) -> list[TextChunk]:
        return _pack_sentences_into_chunks(
            sentences=self._split_into_sentences(text),
            tokenizer=self.tokenizer,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            breadcrumb="",
            chunk_index_start=0,
        )

    def _split_into_sentences(self, text: str) -> list[str]:
        if not text.strip():
            return []
        sentences: list[str] = []
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            for s in self._sbd.segment(paragraph):
                s = s.strip()
                if s:
                    sentences.append(s)
        return sentences


class RegulatoryChunker:
    """Hierarchy-aware chunker for SOPs and regulatory documents.

    Pipeline:
      1. Detect headings (Chapitre, Article, numbered N.N.N, ALL-CAPS).
      2. Group lines into sections under the deepest active heading; each
         section carries a breadcrumb of its ancestor titles.
      3. Pack sentences into ≤chunk_size token windows, never crossing an
         Article boundary unless a single section exceeds 2× chunk_size.
      4. Emit TextChunk records with the breadcrumb attached.

    The optional `document_title` is prepended to every breadcrumb so
    cross-document retrieval still has the source context inline.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        document_title: str = "",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.document_title = document_title.strip()
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        self._sbd = pysbd.Segmenter(language="fr", clean=False)

    def chunk_text(self, text: str) -> list[TextChunk]:
        if not text.strip():
            return []

        sections = self._split_into_sections(text)
        chunks: list[TextChunk] = []
        idx = 0
        for section in sections:
            sentences = self._sentences_in(section.text)
            if not sentences:
                continue
            section_chunks = _pack_sentences_into_chunks(
                sentences=sentences,
                tokenizer=self.tokenizer,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                breadcrumb=section.breadcrumb,
                chunk_index_start=idx,
            )
            chunks.extend(section_chunks)
            idx += len(section_chunks)

        return chunks

    # --- internals --------------------------------------------------------

    def _sentences_in(self, text: str) -> list[str]:
        out: list[str] = []
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            for s in self._sbd.segment(paragraph):
                s = s.strip()
                if s:
                    out.append(s)
        return out

    def _split_into_sections(self, text: str) -> list[_Section]:
        """Walk the document line-by-line; whenever a heading is detected,
        flush the accumulated body under the *previous* breadcrumb and
        push the new heading onto the path."""

        # Path stack: list of (level, label) ordered shallow-to-deep.
        path: list[tuple[int, str]] = []
        current_lines: list[str] = []
        sections: list[_Section] = []
        last_heading_level = -1  # level of the most recent heading, for boundary marking

        def render_breadcrumb() -> str:
            parts: list[str] = []
            if self.document_title:
                parts.append(self.document_title)
            parts.extend(label for _level, label in path)
            return " › ".join(parts)

        def flush() -> None:
            nonlocal current_lines
            body = "\n".join(current_lines).strip()
            if not body:
                current_lines = []
                return
            sections.append(
                _Section(
                    breadcrumb=render_breadcrumb(),
                    text=body,
                    boundary_strength=1 if last_heading_level == 1 else 0,
                )
            )
            current_lines = []

        for line in text.splitlines():
            heading = _detect_heading(line)
            if heading is not None:
                # Flush whatever body was accumulating under the prior path.
                flush()
                # Pop deeper-or-equal levels; this heading replaces them.
                while path and path[-1][0] >= heading.level:
                    path.pop()
                path.append((heading.level, heading.label))
                last_heading_level = heading.level
                continue
            current_lines.append(line)

        flush()

        # Documents with no detected headings yield a single anonymous section.
        if not sections:
            sections.append(
                _Section(breadcrumb=self.document_title or "", text=text.strip())
            )
        return sections


# --- Sentence packing (shared) --------------------------------------------


def _pack_sentences_into_chunks(
    sentences: list[str],
    tokenizer: tiktoken.Encoding,
    chunk_size: int,
    chunk_overlap: int,
    breadcrumb: str,
    chunk_index_start: int,
) -> list[TextChunk]:
    """Greedy sentence packer with sentence-boundary overlap.

    Same algorithm as the original TextChunker, factored out so both
    chunkers share it. Sentences exceeding chunk_size are split at the
    token level as a last resort.
    """
    chunks: list[TextChunk] = []
    current_sentences: list[str] = []
    current_tokens = 0
    next_index = chunk_index_start

    def emit() -> None:
        nonlocal next_index
        if not current_sentences:
            return
        chunks.append(
            TextChunk(
                content=" ".join(current_sentences),
                chunk_index=next_index,
                token_count=current_tokens,
                breadcrumb=breadcrumb,
            )
        )
        next_index += 1

    for sentence in sentences:
        sentence_tokens = len(tokenizer.encode(sentence))

        if sentence_tokens > chunk_size:
            # Flush whatever we have, then hard-split the long sentence by tokens.
            emit()
            current_sentences = []
            current_tokens = 0
            for piece in _split_by_tokens(sentence, tokenizer, chunk_size):
                chunks.append(
                    TextChunk(
                        content=piece,
                        chunk_index=next_index,
                        token_count=len(tokenizer.encode(piece)),
                        breadcrumb=breadcrumb,
                    )
                )
                next_index += 1
            continue

        if current_tokens + sentence_tokens > chunk_size and current_sentences:
            emit()
            # Carry the last few sentences forward as overlap.
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                s_tokens = len(tokenizer.encode(s))
                if overlap_tokens + s_tokens > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += s_tokens
            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    emit()
    return chunks


def _split_by_tokens(
    text: str, tokenizer: tiktoken.Encoding, chunk_size: int
) -> list[str]:
    tokens = tokenizer.encode(text)
    return [
        tokenizer.decode(tokens[i : i + chunk_size])
        for i in range(0, len(tokens), chunk_size)
    ]
