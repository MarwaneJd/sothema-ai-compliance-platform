"""Multi-query retriever (Phase 2).

Runs hybrid retrieval over the original query *plus* N LLM-generated rewrites
in parallel, then fuses the rankings with Reciprocal Rank Fusion. Helps recall
on queries where the user's phrasing differs from the source document's.

Key design: the original-query retrieval is launched **immediately**, in
parallel with the LLM expansion call. Effective latency on the Fast path is
roughly `max(expand_call + retrieve_expansions, retrieve_original)`, not the
sum — so adding multi-query to Fast mode is cheap when most retrievals are
fast and the LLM call is the long pole.
"""

from __future__ import annotations

import asyncio

import numpy as np
import structlog

from app.rag.hybrid_retriever import (
    HybridRetriever,
    RetrievedSegment,
    reciprocal_rank_fusion,
)
from app.rag.query_expander import QueryExpander
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()


class MultiQueryRetriever:
    """Wraps HybridRetriever with LLM-driven query expansion + RRF fusion.

    Audit hook: `last_expanded_queries` holds the rewrites used by the most
    recent retrieve() call. The route handler reads this for audit logging.
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        embedding_service: EmbeddingService,
        query_expander: QueryExpander,
        n_expansions: int = 3,
        rrf_k: int = 60,
    ):
        self.hybrid_retriever = hybrid_retriever
        self.embedding_service = embedding_service
        self.query_expander = query_expander
        self.n_expansions = n_expansions
        self.rrf_k = rrf_k
        self.last_expanded_queries: list[str] = []

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[RetrievedSegment]:
        """Retrieve over `query` + N rewrites, fuse with RRF, return top_k."""

        async def _hybrid(q: str, q_emb: np.ndarray) -> list[RetrievedSegment]:
            return await self.hybrid_retriever.retrieve(
                query=q, query_embedding=q_emb, top_k=top_k
            )

        # Kick off original query retrieval immediately, in parallel with expansion.
        original_emb = await self.embedding_service.embed_query(query)
        original_task = asyncio.create_task(_hybrid(query, original_emb))

        rewrites = await self.query_expander.expand(query, n=self.n_expansions)
        self.last_expanded_queries = rewrites

        # Embed and retrieve each rewrite in parallel.
        async def _rewrite_to_results(rq: str) -> list[RetrievedSegment]:
            emb = await self.embedding_service.embed_query(rq)
            return await _hybrid(rq, emb)

        rewrite_tasks = [asyncio.create_task(_rewrite_to_results(r)) for r in rewrites]

        original_results = await original_task
        rewrite_results = (
            await asyncio.gather(*rewrite_tasks) if rewrite_tasks else []
        )

        # Build per-source rankings keyed by vs_id.
        all_rankings: list[dict[str, int]] = []
        all_segments_by_id: dict[str, RetrievedSegment] = {}

        for results in [original_results, *rewrite_results]:
            ranking: dict[str, int] = {}
            for rank, r in enumerate(results, start=1):
                ranking[r.vector_store_id] = rank
                # Keep the first occurrence's rank metadata; RRF score gets recomputed.
                all_segments_by_id.setdefault(r.vector_store_id, r)
            if ranking:
                all_rankings.append(ranking)

        if not all_rankings:
            return []

        fused = reciprocal_rank_fusion(all_rankings, k=self.rrf_k, top_k=top_k)

        result = [
            RetrievedSegment(
                vector_store_id=vs_id,
                rrf_score=score,
                vector_rank=all_segments_by_id[vs_id].vector_rank,
                bm25_rank=all_segments_by_id[vs_id].bm25_rank,
            )
            for vs_id, score in fused
            if vs_id in all_segments_by_id
        ]

        logger.info(
            "Multi-query retrieval complete",
            n_rewrites=len(rewrites),
            fused_results=len(result),
        )
        return result
