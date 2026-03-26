import pytest

from app.services.chunking import TextChunker


class TestTextChunker:
    def setup_method(self):
        self.chunker = TextChunker(chunk_size=50, chunk_overlap=10)

    def test_empty_text(self):
        chunks = self.chunker.chunk_text("")
        assert chunks == []

    def test_whitespace_only(self):
        chunks = self.chunker.chunk_text("   \n\n   ")
        assert chunks == []

    def test_short_text_single_chunk(self):
        text = "This is a short text."
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0

    def test_chunk_indices_sequential(self):
        # Create text long enough for multiple chunks
        text = "This is a sentence. " * 50
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_size_respected(self):
        text = "This is a test sentence for chunking. " * 100
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text(text)
        for chunk in chunks:
            assert chunk.token_count <= 110  # Allow small margin

    def test_overlap_produces_more_chunks(self):
        text = "Word " * 200
        no_overlap = TextChunker(chunk_size=50, chunk_overlap=0)
        with_overlap = TextChunker(chunk_size=50, chunk_overlap=10)
        chunks_no = no_overlap.chunk_text(text)
        chunks_with = with_overlap.chunk_text(text)
        assert len(chunks_with) >= len(chunks_no)

    def test_paragraph_splitting(self):
        text = "First paragraph content.\n\nSecond paragraph content."
        chunker = TextChunker(chunk_size=500, chunk_overlap=0)
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 1

    def test_token_count_positive(self):
        text = "Every chunk should have a positive token count."
        chunks = self.chunker.chunk_text(text)
        for chunk in chunks:
            assert chunk.token_count > 0
