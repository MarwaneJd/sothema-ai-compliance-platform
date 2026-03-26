import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from app.core.exceptions import EmbeddingError

logger = structlog.get_logger()


class EmbeddingService:
    """Local embedding generation using sentence-transformers (all-MiniLM-L6-v2).

    Free, open-source, runs on CPU. No API calls or Azure costs.
    Produces 384-dimensional vectors.
    """

    def __init__(self, model: SentenceTransformer):
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for a list of texts. Returns L2-normalized vectors."""
        if not texts:
            return []

        try:
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=True,  # L2-normalize for cosine sim via inner product
                show_progress_bar=False,
            )

            vectors = [vec.astype(np.float32) for vec in embeddings]

            logger.info("Embeddings generated", count=len(vectors))
            return vectors

        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

    async def embed_query(self, query: str) -> np.ndarray:
        """Generate a single embedding for a search query."""
        try:
            embedding = self.model.encode(
                query,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding.astype(np.float32)

        except Exception as e:
            logger.error("Query embedding failed", error=str(e))
            raise EmbeddingError(f"Query embedding failed: {e}") from e
