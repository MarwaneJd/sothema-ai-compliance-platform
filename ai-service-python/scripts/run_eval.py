"""Run the retrieval eval against the local indexes.

Loads everything the same way `app.main`'s FastAPI lifespan does
(embedding model, FAISS, BM25), opens a DB session, walks the goldset,
prints metrics. No HTTP server needed.

Usage:
    python -m scripts.run_eval                  # default settings
    python -m scripts.run_eval --top-k 5
    python -m scripts.run_eval --goldset path/to/custom.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import settings
from app.evals import evaluate_retrieval, load_goldset

if TYPE_CHECKING:
    from app.rag.pipeline import RAGPipeline

# DB and heavy ML imports are deferred to main_async() so `--help` works
# without a live database / installed drivers.

DEFAULT_GOLDSET = Path(__file__).parent.parent / "app" / "evals" / "goldset.jsonl"


class _PipelineRetrieverProbe:
    """Adapts a full RAGPipeline to the RetrieverProtocol the eval expects."""

    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline

    async def retrieve_ids(self, query: str, top_k: int) -> list[str]:
        # `retrieve_only` skips the LLM call — exactly what the
        # retrieval eval needs.
        resp = await self.pipeline.retrieve_only(question=query, top_k=top_k)
        return [seg.VectorStoreId for seg in resp.segments if seg.VectorStoreId]


async def _run(pipeline: RAGPipeline, goldset_path: Path, top_k: int) -> dict[str, float]:
    goldset = load_goldset(goldset_path)
    if not goldset:
        print(f"  ⚠ Goldset at {goldset_path} is empty — nothing to evaluate.")
        print("  Bootstrap entries with: python -m app.evals.bootstrap")
        return {}

    print(f"\nRunning over {len(goldset)} queries (top_k={top_k}) ...")
    t0 = time.perf_counter()
    probe = _PipelineRetrieverProbe(pipeline)
    metrics = await evaluate_retrieval(goldset, probe, top_k=top_k)
    elapsed = time.perf_counter() - t0
    print(f"Done in {elapsed:.1f}s ({elapsed / len(goldset) * 1000:.0f} ms/query)\n")
    return metrics


def _print_metrics(metrics: dict[str, float]) -> None:
    if not metrics:
        return
    print(f"{'Metric':<14}  Value")
    print("-" * 24)
    for k in sorted(metrics):
        if k == "n_queries":
            continue
        print(f"{k:<14}  {metrics[k]:.4f}")
    print(f"\nn_queries: {int(metrics.get('n_queries', 0))}")


async def main_async(args) -> int:
    # Deferred imports — keep `--help` cheap and DB-free.
    from sentence_transformers import SentenceTransformer

    from app.db.repositories import TextSegmentRepository
    from app.db.session import get_db
    from app.rag.bm25_store import BM25Store
    from app.rag.hybrid_retriever import HybridRetriever
    from app.rag.pipeline import RAGPipeline
    from app.rag.vector_store import FAISSVectorStore
    from app.services.embedding import EmbeddingService

    print(f"Loading embedding model: {settings.embedding_model_name}")
    embedding_model = SentenceTransformer(settings.embedding_model_name)
    embedding_service = EmbeddingService(embedding_model)

    print(f"Loading FAISS index from {settings.faiss_index_path}")
    vector_store = FAISSVectorStore(
        index_path=settings.faiss_index_path,
        dimensions=settings.embedding_dimensions,
    )
    vector_store.load()
    print(f"  → {vector_store.size:,d} vectors")

    bm25_store = BM25Store()
    bm25_store.load(f"{settings.faiss_index_path}/bm25_index.pkl")
    print(f"  → {bm25_store.size:,d} BM25 docs")

    if vector_store.size == 0 or bm25_store.size == 0:
        print(
            "\n⚠ One or both indexes are empty. Re-ingest documents before running eval.",
            file=sys.stderr,
        )
        return 1

    hybrid = HybridRetriever(
        vector_store=vector_store, bm25_store=bm25_store, k=settings.rrf_k
    )

    async for session in get_db():
        seg_repo = TextSegmentRepository(session)
        pipeline = RAGPipeline(
            hybrid_retriever=hybrid,
            embedding_service=embedding_service,
            llm_service=None,  # type: ignore[arg-type]  # retrieve_only doesn't need LLM
            segment_repo=seg_repo,
        )
        metrics = await _run(pipeline, args.goldset, args.top_k)
        _print_metrics(metrics)
        break

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goldset",
        type=Path,
        default=DEFAULT_GOLDSET,
        help=f"Path to goldset JSONL (default: {DEFAULT_GOLDSET})",
    )
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
