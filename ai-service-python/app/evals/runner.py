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


async def evaluate_retrieval(
    goldset: Iterable[GoldEntry],
    retriever: RetrieverProtocol,
    top_k: int = 10,
    metrics: tuple[str, ...] = ("recall@5", "recall@10", "mrr@10", "ndcg@10"),
) -> dict[str, float]:
    """Run the retriever over the goldset and compute aggregate metrics.

    Empty goldset returns `{"n_queries": 0}` so CI doesn't fail before
    labeled data lands.
    """
    from ranx import Qrels, Run, evaluate  # local import — keeps cold start fast

    qrels_dict: dict[str, dict[str, int]] = {}
    run_dict: dict[str, dict[str, float]] = {}

    n = 0
    for entry in goldset:
        n += 1
        # Qrels: relevance judgments. All gold ids are equally relevant (1).
        qrels_dict[entry.id] = {seg_id: 1 for seg_id in entry.relevant_segment_ids}

        retrieved = await retriever.retrieve_ids(entry.query, top_k=top_k)
        # ranx expects a score per doc; we use reciprocal-rank as the score
        # because we only have an ordering, not a normalized model score.
        run_dict[entry.id] = {
            doc_id: 1.0 / (rank + 1) for rank, doc_id in enumerate(retrieved)
        }

    if n == 0:
        logger.warning("Empty goldset — no metrics to compute")
        return {"n_queries": 0}

    qrels = Qrels(qrels_dict)
    run = Run(run_dict)
    raw_results = evaluate(qrels, run, list(metrics))
    # ranx returns a bare scalar when given exactly one metric, dict otherwise.
    if isinstance(raw_results, dict):
        results = {k: float(v) for k, v in raw_results.items()}
    else:
        results = {metrics[0]: float(raw_results)}
    results["n_queries"] = float(n)
    logger.info("Retrieval eval complete", **results)
    return results
