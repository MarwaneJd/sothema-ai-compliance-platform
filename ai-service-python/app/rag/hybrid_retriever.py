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
    # Normalized cross-encoder relevance in [0,1], set when a reranker ran.
    # None ⇒ no rerank, so the only score available is the (tiny) RRF value.
    rerank_score: float | None = None


def reciprocal_rank_fusion(
    rankings: list[dict[str, int]],
    k: int = 60,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion across an arbitrary number of ranked id lists.

    Each input dict maps `vector_store_id -> rank` (1-indexed). Items missing
    from a ranking contribute 0 from that source. Returns `(id, score)` tuples
    sorted by fused score descending. If `top_k` is given, truncates.

    Used by both `HybridRetriever` (vector + BM25) and `MultiQueryRetriever`
    (one ranking per rewritten query).
    """
    if not rankings:
        return []
    all_ids: set[str] = set()
    for r in rankings:
        all_ids.update(r.keys())

    scores: dict[str, float] = {}
    for vs_id in all_ids:
        score = 0.0
        for r in rankings:
            rank = r.get(vs_id)
            if rank is not None:
                score += 1.0 / (k + rank)
        scores[vs_id] = score

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    if top_k is not None:
        sorted_ids = sorted_ids[:top_k]
    return [(vs_id, scores[vs_id]) for vs_id in sorted_ids]


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
        fused = reciprocal_rank_fusion(
            [vector_ranks, bm25_ranks], k=self.k, top_k=top_k
        )

        results = [
            RetrievedSegment(
                vector_store_id=vs_id,
                rrf_score=score,
                vector_rank=vector_ranks.get(vs_id),
                bm25_rank=bm25_ranks.get(vs_id),
            )
            for vs_id, score in fused
        ]

        logger.info(
            "Hybrid retrieval complete",
            vector_results=len(vector_results),
            bm25_results=len(bm25_results),
            fused_results=len(results),
        )

        return results
