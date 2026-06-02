"""Cross-encoder reranker for hybrid retrieval results.

Wraps `sentence_transformers.CrossEncoder` to score (query, candidate) pairs
and reorder a candidate set. Loaded once at startup via app.state — model
weights (~568MB for bge-reranker-v2-m3) are downloaded by HuggingFace on
first run and cached locally.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

import structlog
from sentence_transformers import CrossEncoder

from app.rag.hybrid_retriever import RetrievedSegment

logger = structlog.get_logger()


def _sigmoid(x: float) -> float:
    """Map a cross-encoder logit to a [0,1] relevance via sigmoid. Monotonic, so
    it preserves the reranked order; this is the value surfaced to the API as the
    relevance score (raw logits run roughly -11..+11 for this model)."""
    return 1.0 / (1.0 + math.exp(-x))


@dataclass
class RerankedSegment:
    vector_store_id: str
    rerank_score: float  # raw cross-encoder logit (kept for logging)
    relevance: float  # sigmoid(rerank_score) in [0,1] — display relevance
    rrf_score: float
    vector_rank: int | None
    bm25_rank: int | None


class CrossEncoderReranker:
    """Multilingual cross-encoder reranker (FR/AR/EN) for the regulatory corpus."""

    def __init__(self, model: CrossEncoder, model_name: str):
        self._model = model
        self._model_name = model_name
        logger.info("Cross-encoder reranker initialized", model=model_name)

    @classmethod
    def load(cls, model_name: str, max_length: int = 256) -> CrossEncoderReranker:
        model = CrossEncoder(model_name, max_length=max_length)
        return cls(model=model, model_name=model_name)

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedSegment],
        candidate_texts: list[str],
        top_n: int,
    ) -> list[RerankedSegment]:
        """Rerank candidates by cross-encoder relevance and return top_n.

        `candidate_texts[i]` must be the textual content for `candidates[i]` —
        the cross-encoder needs the full text, not just the id. Caller is
        responsible for fetching texts (typically from `TextSegmentRepository`).
        """
        if not candidates or not candidate_texts:
            return []
        if len(candidates) != len(candidate_texts):
            raise ValueError(
                f"candidates ({len(candidates)}) and candidate_texts ({len(candidate_texts)}) length mismatch"
            )

        pairs = [(query, text) for text in candidate_texts]

        # CrossEncoder.predict is sync + CPU-bound — push to a thread so we don't
        # block the event loop on a 50-pair batch (~150ms on CPU).
        scores = await asyncio.to_thread(self._model.predict, pairs)

        scored = [
            RerankedSegment(
                vector_store_id=cand.vector_store_id,
                rerank_score=float(score),
                relevance=_sigmoid(float(score)),
                rrf_score=cand.rrf_score,
                vector_rank=cand.vector_rank,
                bm25_rank=cand.bm25_rank,
            )
            for cand, score in zip(candidates, scores, strict=True)
        ]
        scored.sort(key=lambda s: s.rerank_score, reverse=True)

        result = scored[:top_n]
        logger.info(
            "Rerank complete",
            candidate_count=len(candidates),
            returned=len(result),
            top_score=result[0].rerank_score if result else None,
        )
        return result
