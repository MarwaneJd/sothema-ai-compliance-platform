from dataclasses import dataclass

import tiktoken


@dataclass
class TextChunk:
    content: str
    chunk_index: int
    token_count: int


class TextChunker:
    """Token-aware text chunking using tiktoken."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")

    def chunk_text(self, text: str) -> list[TextChunk]:
        if not text.strip():
            return []

        sentences = self._split_into_sentences(text)
        chunks: list[TextChunk] = []
        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))

            # If a single sentence exceeds chunk size, split it by tokens
            if sentence_tokens > self.chunk_size:
                # Flush current buffer first
                if current_sentences:
                    chunk_text = " ".join(current_sentences)
                    chunks.append(
                        TextChunk(
                            content=chunk_text,
                            chunk_index=len(chunks),
                            token_count=current_tokens,
                        )
                    )
                    current_sentences = []
                    current_tokens = 0

                # Split the long sentence by tokens
                token_chunks = self._split_by_tokens(sentence)
                for tc in token_chunks:
                    chunks.append(
                        TextChunk(
                            content=tc,
                            chunk_index=len(chunks),
                            token_count=len(self.tokenizer.encode(tc)),
                        )
                    )
                continue

            # Check if adding this sentence would exceed the chunk size
            if current_tokens + sentence_tokens > self.chunk_size and current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(
                    TextChunk(
                        content=chunk_text,
                        chunk_index=len(chunks),
                        token_count=current_tokens,
                    )
                )

                # Keep overlap: rewind to include the last few sentences
                overlap_sentences: list[str] = []
                overlap_tokens = 0
                for s in reversed(current_sentences):
                    s_tokens = len(self.tokenizer.encode(s))
                    if overlap_tokens + s_tokens > self.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens

                current_sentences = overlap_sentences
                current_tokens = overlap_tokens

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Final chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunks.append(
                TextChunk(
                    content=chunk_text,
                    chunk_index=len(chunks),
                    token_count=current_tokens,
                )
            )

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences on paragraph and sentence boundaries."""
        import re

        # Split on double newlines first (paragraphs)
        paragraphs = re.split(r"\n\s*\n", text)
        sentences = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # Split on sentence-ending punctuation followed by space
            parts = re.split(r"(?<=[.!?])\s+", para)
            for part in parts:
                part = part.strip()
                if part:
                    sentences.append(part)
        return sentences

    def _split_by_tokens(self, text: str) -> list[str]:
        """Split a long text into chunks of at most chunk_size tokens."""
        tokens = self.tokenizer.encode(text)
        result = []
        for i in range(0, len(tokens), self.chunk_size):
            chunk_tokens = tokens[i : i + self.chunk_size]
            result.append(self.tokenizer.decode(chunk_tokens))
        return result
