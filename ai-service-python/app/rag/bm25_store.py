import os
import pickle

import structlog
from rank_bm25 import BM25Okapi

logger = structlog.get_logger()


class BM25Store:
    """BM25 keyword search index with serialization."""

    def __init__(self) -> None:
        self.bm25: BM25Okapi | None = None
        self.corpus_ids: list[str] = []  # VectorStoreId strings, parallel to tokenized corpus
        self.corpus_texts: list[list[str]] = []  # Tokenized texts

    @property
    def size(self) -> int:
        return len(self.corpus_ids)

    def build_index(self, texts: list[str], vector_store_ids: list[str]) -> None:
        """Build a new BM25 index from texts and their VectorStoreIds."""
        tokenized = [self._tokenize(text) for text in texts]
        self.corpus_texts = tokenized
        self.corpus_ids = list(vector_store_ids)
        self.bm25 = BM25Okapi(tokenized)
        logger.info("BM25 index built", size=len(texts))

    def add_documents(self, texts: list[str], vector_store_ids: list[str]) -> None:
        """Add new documents and rebuild the index."""
        new_tokenized = [self._tokenize(text) for text in texts]
        self.corpus_texts.extend(new_tokenized)
        self.corpus_ids.extend(vector_store_ids)
        # BM25Okapi doesn't support incremental add, must rebuild
        self.bm25 = BM25Okapi(self.corpus_texts)
        logger.info("BM25 documents added", new_count=len(texts), total=len(self.corpus_ids))

    def remove_documents(self, vector_store_ids: set[str]) -> None:
        """Remove documents by VectorStoreId and rebuild index."""
        if not vector_store_ids:
            return

        filtered = [
            (text, vs_id)
            for text, vs_id in zip(self.corpus_texts, self.corpus_ids)
            if vs_id not in vector_store_ids
        ]

        if filtered:
            self.corpus_texts, self.corpus_ids = zip(*filtered)  # type: ignore[assignment]
            self.corpus_texts = list(self.corpus_texts)
            self.corpus_ids = list(self.corpus_ids)
            self.bm25 = BM25Okapi(self.corpus_texts)
        else:
            self.corpus_texts = []
            self.corpus_ids = []
            self.bm25 = None

        logger.info("BM25 documents removed", removed=len(vector_store_ids))

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search the BM25 index. Returns list of (VectorStoreId, BM25_score)."""
        if self.bm25 is None or not self.corpus_ids:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices sorted by score descending
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :top_k
        ]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.corpus_ids[idx], float(scores[idx])))

        return results

    def load(self, path: str) -> None:
        """Load serialized BM25 index from disk."""
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                self.corpus_texts = data["corpus_texts"]
                self.corpus_ids = data["corpus_ids"]
                if self.corpus_texts:
                    self.bm25 = BM25Okapi(self.corpus_texts)
                logger.info("BM25 index loaded", size=len(self.corpus_ids))
            except Exception as e:
                logger.error("Failed to load BM25 index", error=str(e))
                self.bm25 = None
                self.corpus_ids = []
                self.corpus_texts = []
        else:
            logger.info("No existing BM25 index found")

    def save(self, path: str) -> None:
        """Save BM25 index to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "corpus_texts": self.corpus_texts,
            "corpus_ids": self.corpus_ids,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("BM25 index saved", size=len(self.corpus_ids))

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercase tokenization."""
        return text.lower().split()
