"""Retrieval evaluation runner.

Computes ranx metrics — recall@k, MRR@10, nDCG@10 — by feeding a goldset
through any object that conforms to a `RetrieverProtocol`. The hybrid
retriever in `app.rag.hybrid_retriever` satisfies this via a thin wrapper
when called with a real query embedding.

Wrap the call in your own script with the FastAPI app's services:

    from app.evals import load_goldset, evaluate_retrieval
    from app.evals.runner import HybridRetrieverProbe

    probe = HybridRetrieverProbe(hybrid_retriever, embedding_service)
    metrics = await evaluate_retrieval(load_goldset("goldset.jsonl"), probe, top_k=10)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Protocol

import structlog

from app.evals.goldset import GoldEntry

logger = structlog.get_logger()


class RetrieverProtocol(Protocol):
    """Anything that takes a query string + top_k and returns ranked
    `vector_store_id` strings. The hybrid retriever wrapped via
    `HybridRetrieverProbe` satisfies this."""

    async def retrieve_ids(self, query: str, top_k: int) -> list[str]:
        ...


@dataclass
class HybridRetrieverProbe:
    """Adapts the production HybridRetriever to RetrieverProtocol — the
    eval doesn't care about RRF scores or per-rank diagnostics, just the
    ranked id list."""

    hybrid_retriever: object  # app.rag.hybrid_retriever.HybridRetriever
    embedding_service: object  # app.services.embedding.EmbeddingService

    async def retrieve_ids(self, query: str, top_k: int) -> list[str]:
        embedding = await self.embedding_service.embed_query(query)  # type: ignore[attr-defined]
        results = await self.hybrid_retriever.retrieve(  # type: ignore[attr-defined]
            query=query, query_embedding=embedding, top_k=top_k
        )
        return [r.vector_store_id for r in results]


@dataclass
class RerankedRetrieverProbe:
    """Hybrid retrieve + cross-encoder rerank, projected to the ranked id list.

    Mirrors `HybridRetrieverProbe` so eval results before/after Phase 1 are
    directly comparable. Fetches `top_k * fetch_multiplier` candidates from
    hybrid retrieval, then reranks to `top_k` using the cross-encoder.
    """

    hybrid_retriever: object  # app.rag.hybrid_retriever.HybridRetriever
    embedding_service: object  # app.services.embedding.EmbeddingService
    reranker: object  # app.rag.reranker.CrossEncoderReranker
    segment_repo: object  # app.db.repositories.TextSegmentRepository
    fetch_multiplier: int = 4

    async def retrieve_ids(self, query: str, top_k: int) -> list[str]:
        embedding = await self.embedding_service.embed_query(query)  # type: ignore[attr-defined]
        fetch_k = top_k * self.fetch_multiplier
        candidates = await self.hybrid_retriever.retrieve(  # type: ignore[attr-defined]
            query=query, query_embedding=embedding, top_k=fetch_k
        )
        if not candidates:
            return []

        ids = [c.vector_store_id for c in candidates]
        segments = await self.segment_repo.get_by_vector_store_ids(ids)  # type: ignore[attr-defined]
        seg_by_id = {s.VectorStoreId: s for s in segments if s.VectorStoreId}

        aligned_candidates = []
        aligned_texts = []
        for c in candidates:
            seg = seg_by_id.get(c.vector_store_id)
            if seg is None:
                continue
            aligned_candidates.append(c)
            aligned_texts.append(seg.Content)

        reranked = await self.reranker.rerank(  # type: ignore[attr-defined]
            query=query,
            candidates=aligned_candidates,
            candidate_texts=aligned_texts,
            top_n=top_k,
        )
        return [r.vector_store_id for r in reranked]


@dataclass
class MultiQueryRetrieverProbe:
    """Multi-query expansion + hybrid retrieve + (optional) rerank.

    When `reranker` and `segment_repo` are provided, runs the full Phase 1+2
    Fast-mode pipeline. When omitted, runs multi-query without reranking — useful
    for isolating Phase 2's contribution on top of Phase 1 in eval reports.
    """

    multi_query_retriever: object  # app.rag.multi_query.MultiQueryRetriever
    fetch_multiplier: int = 4
    reranker: object | None = None  # app.rag.reranker.CrossEncoderReranker
    segment_repo: object | None = None  # app.db.repositories.TextSegmentRepository

    async def retrieve_ids(self, query: str, top_k: int) -> list[str]:
        fetch_k = top_k * self.fetch_multiplier if self.reranker else top_k
        candidates = await self.multi_query_retriever.retrieve(  # type: ignore[attr-defined]
            query=query, top_k=fetch_k
        )
        if not candidates:
            return []
        if self.reranker is None or self.segment_repo is None:
            return [c.vector_store_id for c in candidates[:top_k]]

        ids = [c.vector_store_id for c in candidates]
        segments = await self.segment_repo.get_by_vector_store_ids(ids)  # type: ignore[attr-defined]
        seg_by_id = {s.VectorStoreId: s for s in segments if s.VectorStoreId}

        aligned_candidates = []
        aligned_texts = []
        for c in candidates:
            seg = seg_by_id.get(c.vector_store_id)
            if seg is None:
                continue
            aligned_candidates.append(c)
            aligned_texts.append(seg.Content)

        reranked = await self.reranker.rerank(  # type: ignore[attr-defined]
            query=query,
            candidates=aligned_candidates,
            candidate_texts=aligned_texts,
            top_n=top_k,
        )
        return [r.vector_store_id for r in reranked]


def _parse_metric(name: str) -> tuple[str, int]:
    """'recall@10' -> ('recall', 10). Cutoff is required."""
    base, _, cut = name.partition("@")
    if not cut:
        raise ValueError(f"metric {name!r} must specify a cutoff, e.g. '{name}@10'")
    return base.lower(), int(cut)


def _score_query(metric: str, k: int, ranked: list[str], gold: set[str]) -> float:
    """Single-query metric, binary relevance.

    - recall@k : |gold ∩ top-k| / |gold|
    - mrr@k    : 1 / rank of first relevant in top-k (1-indexed), else 0
    - ndcg@k   : DCG@k / IDCG@k, gain 1 per relevant, discount 1/log2(rank+1)
    """
    if not gold:
        return 0.0
    topk = ranked[:k]
    if metric == "recall":
        hits = sum(1 for d in topk if d in gold)
        return hits / len(gold)
    if metric == "mrr":
        for i, d in enumerate(topk, start=1):
            if d in gold:
                return 1.0 / i
        return 0.0
    if metric == "ndcg":
        dcg = sum(
            1.0 / math.log2(i + 1)
            for i, d in enumerate(topk, start=1)
            if d in gold
        )
        ideal_hits = min(len(gold), k)
        idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
        return dcg / idcg if idcg > 0 else 0.0
    raise ValueError(f"unsupported metric base {metric!r}")


async def evaluate_retrieval(
    goldset: Iterable[GoldEntry],
    retriever: RetrieverProtocol,
    top_k: int = 10,
    metrics: tuple[str, ...] = ("recall@5", "recall@10", "mrr@10", "ndcg@10"),
) -> dict[str, float]:
    """Run the retriever over the goldset and compute aggregate metrics.

    Metrics are computed in-house (recall@k / MRR@k / nDCG@k, binary
    relevance) — no `ranx`. `ranx` pulls the `zlib-state` C extension which
    won't build in the slim runtime image, so the harness could never run in
    Docker/CI. Same rationale as the hand-rolled `judge.py` (avoids a fragile
    heavy dep for a few textbook formulas).

    Empty goldset returns `{"n_queries": 0}` so CI doesn't fail before
    labeled data lands.
    """
    parsed = [(name, *_parse_metric(name)) for name in metrics]

    per_metric_sums: dict[str, float] = {name: 0.0 for name in metrics}
    n = 0
    for entry in goldset:
        n += 1
        gold = set(entry.relevant_segment_ids)
        ranked = await retriever.retrieve_ids(entry.query, top_k=top_k)
        for name, base, k in parsed:
            per_metric_sums[name] += _score_query(base, k, ranked, gold)

    if n == 0:
        logger.warning("Empty goldset — no metrics to compute")
        return {"n_queries": 0}

    results: dict[str, float] = {
        name: per_metric_sums[name] / n for name in metrics
    }
    results["n_queries"] = float(n)
    logger.info("Retrieval eval complete", **results)
    return results
