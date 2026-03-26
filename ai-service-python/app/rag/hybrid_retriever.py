from dataclasses import dataclass

import numpy as np
import structlog

from app.rag.bm25_store import BM25Store
from app.rag.vector_store import FAISSVectorStore

logger = structlog.get_logger()


@dataclass
class RetrievedSegment:
    vector_store_id: str
    rrf_score: float
    vector_rank: int | None
    bm25_rank: int | None


class HybridRetriever:
    """Combines FAISS vector search and BM25 keyword search using Reciprocal Rank Fusion."""

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        bm25_store: BM25Store,
        k: int = 60,
    ):
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.k = k  # RRF constant

    async def retrieve(
        self,
        query: str,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> list[RetrievedSegment]:
        """Hybrid retrieval with Reciprocal Rank Fusion.

        1. Get 2*top_k results from vector search
        2. Get 2*top_k results from BM25 search
        3. Fuse using RRF: score = sum(1 / (k + rank))
        4. Return top_k by fused score
        """
        fetch_k = top_k * 2

        # Vector search
        vector_results = self.vector_store.search(query_embedding, top_k=fetch_k)
        vector_ranks: dict[str, int] = {}
        for rank, (vs_id, _score) in enumerate(vector_results, start=1):
            vector_ranks[vs_id] = rank

        # BM25 search
        bm25_results = self.bm25_store.search(query, top_k=fetch_k)
        bm25_ranks: dict[str, int] = {}
        for rank, (vs_id, _score) in enumerate(bm25_results, start=1):
            bm25_ranks[vs_id] = rank

        # Reciprocal Rank Fusion
        all_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
        rrf_scores: dict[str, float] = {}

        for vs_id in all_ids:
            score = 0.0
            if vs_id in vector_ranks:
                score += 1.0 / (self.k + vector_ranks[vs_id])
            if vs_id in bm25_ranks:
                score += 1.0 / (self.k + bm25_ranks[vs_id])
            rrf_scores[vs_id] = score

        # Sort by RRF score descending, take top_k
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[
            :top_k
        ]

        results = [
            RetrievedSegment(
                vector_store_id=vs_id,
                rrf_score=rrf_scores[vs_id],
                vector_rank=vector_ranks.get(vs_id),
                bm25_rank=bm25_ranks.get(vs_id),
            )
            for vs_id in sorted_ids
        ]

        logger.info(
            "Hybrid retrieval complete",
            vector_results=len(vector_results),
            bm25_results=len(bm25_results),
            fused_results=len(results),
        )

        return results
