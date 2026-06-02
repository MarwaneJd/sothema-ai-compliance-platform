from dataclasses import dataclass

import structlog

from app.db.models import TextSegment
from app.db.repositories import TextSegmentRepository
from app.rag.hybrid_retriever import HybridRetriever, RetrievedSegment
from app.rag.multi_query import MultiQueryRetriever
from app.rag.reranker import CrossEncoderReranker
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService

logger = structlog.get_logger()


def _display_score(r: RetrievedSegment | None) -> float:
    """Relevance shown to the user: the normalized cross-encoder score when a
    reranker ran, else the RRF score. Raw RRF is a rank-fusion number bounded
    near n/(k+1) (~5-7% here) and is misleading as a relevance percentage."""
    if r is None:
        return 0.0
    return r.rerank_score if r.rerank_score is not None else r.rrf_score


SYSTEM_PROMPT = """You are a pharmaceutical regulatory compliance assistant.

STRICT RULES:
- Answer ONLY using facts present in the "Context documents" below.
- DO NOT use general knowledge, training data, or any external information.
- DO NOT infer, extrapolate, or fill gaps from prior knowledge of regulations
  (BPF, GMP, ICH, FDA, EMA, etc.). If the specific fact is not in the context,
  it is not in your answer.
- If the context does not contain the answer — even partially — respond exactly
  with one of these (matching the question's language):
    French:  "Cette information n'est pas couverte par les documents disponibles."
    English: "This information is not covered by the available documents."
    Arabic:  "هذه المعلومة غير مغطاة في الوثائق المتاحة."
  Do not append speculation, "however", or "in general" after this sentence.

CITATION FORMAT:
- For every factual claim, cite inline as [Source N] where N is the chunk
  index shown in the context header (e.g. "[Source: ..., Chunk 12]" → cite as [Source 12]).
- Cite only chunk indices that appear in the context. Never invent indices.
- Multiple sources for one claim: [Source 3, Source 7].

Answer in the same language as the question."""


@dataclass
class SourceReference:
    document_id: str
    document_title: str
    chunk_index: int
    content_preview: str
    relevance_score: float


@dataclass
class RAGResponse:
    answer: str
    sources: list[SourceReference]
    segments: list[TextSegment]


class RAGPipeline:
    """End-to-end RAG pipeline: embed query → hybrid retrieve → build context → LLM → answer."""

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        segment_repo: TextSegmentRepository,
        reranker: CrossEncoderReranker | None = None,
        reranker_fetch_multiplier: int = 4,
        multi_query_retriever: MultiQueryRetriever | None = None,
    ):
        self.hybrid_retriever = hybrid_retriever
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.segment_repo = segment_repo
        self.reranker = reranker
        self.reranker_fetch_multiplier = reranker_fetch_multiplier
        self.multi_query_retriever = multi_query_retriever

    async def _retrieve_and_rerank(
        self, question: str, top_k: int
    ) -> tuple[list[RetrievedSegment], list[TextSegment]]:
        """Hybrid (or multi-query) retrieve, then optionally rerank.

        When the reranker is active, fetches `top_k * fetch_multiplier` candidates
        from the upstream retriever and reorders them; the candidate text needed
        for cross-encoder scoring is loaded from the segment repository in the
        same DB round-trip we'd do anyway.
        """
        fetch_k = top_k * self.reranker_fetch_multiplier if self.reranker else top_k

        if self.multi_query_retriever is not None:
            retrieved = await self.multi_query_retriever.retrieve(
                query=question, top_k=fetch_k
            )
        else:
            query_embedding = await self.embedding_service.embed_query(question)
            retrieved = await self.hybrid_retriever.retrieve(
                query=question,
                query_embedding=query_embedding,
                top_k=fetch_k,
            )

        if not retrieved:
            return [], []

        vector_store_ids = [r.vector_store_id for r in retrieved]
        segments = await self.segment_repo.get_by_vector_store_ids(vector_store_ids)
        segment_map = {s.VectorStoreId: s for s in segments if s.VectorStoreId}

        if self.reranker is None:
            ordered_segments = [
                segment_map[vs_id] for vs_id in vector_store_ids if vs_id in segment_map
            ]
            return retrieved[: len(ordered_segments)], ordered_segments

        # Align candidates with their texts for the cross-encoder.
        aligned_candidates: list[RetrievedSegment] = []
        aligned_texts: list[str] = []
        for r in retrieved:
            seg = segment_map.get(r.vector_store_id)
            if seg is None:
                continue
            aligned_candidates.append(r)
            aligned_texts.append(seg.Content)

        reranked = await self.reranker.rerank(
            query=question,
            candidates=aligned_candidates,
            candidate_texts=aligned_texts,
            top_n=top_k,
        )

        # Project reranked output back into the (RetrievedSegment, TextSegment) shape
        # the rest of the pipeline expects. RRF score is preserved from the upstream
        # hybrid call so audit/UI views still see it; rerank score logged separately.
        rrf_by_id = {r.vector_store_id: r for r in retrieved}
        final_retrieved: list[RetrievedSegment] = []
        final_segments: list[TextSegment] = []
        for rr in reranked:
            seg = segment_map.get(rr.vector_store_id)
            base = rrf_by_id.get(rr.vector_store_id)
            if seg is None or base is None:
                continue
            base.rerank_score = rr.relevance
            final_retrieved.append(base)
            final_segments.append(seg)
        return final_retrieved, final_segments

    async def retrieve_only(self, question: str, top_k: int = 6) -> RAGResponse:
        """Hybrid retrieval without LLM — fast, free, fully transparent.
        Same shape as `query()` but `answer` is empty."""

        retrieved, ordered_segments = await self._retrieve_and_rerank(question, top_k)

        if not retrieved:
            return RAGResponse(answer="", sources=[], segments=[])

        rrf_map = {r.vector_store_id: r for r in retrieved}

        sources: list[SourceReference] = []
        for segment in ordered_segments:
            doc = segment.document
            doc_title = doc.Title if doc else "Unknown"
            rrf_result = rrf_map.get(segment.VectorStoreId)
            sources.append(
                SourceReference(
                    document_id=str(segment.DocumentId),
                    document_title=doc_title,
                    chunk_index=segment.ChunkIndex,
                    content_preview=segment.Content[:500],
                    relevance_score=_display_score(rrf_result),
                )
            )

        logger.info(
            "Retrieval-only search complete",
            question_preview=question[:100],
            sources_count=len(sources),
        )
        return RAGResponse(answer="", sources=sources, segments=ordered_segments)

    async def query(self, question: str, top_k: int = 6) -> RAGResponse:
        retrieved, ordered_segments = await self._retrieve_and_rerank(question, top_k)

        if not retrieved:
            return RAGResponse(
                answer="No relevant documents found for your query.",
                sources=[],
                segments=[],
            )

        rrf_map = {r.vector_store_id: r for r in retrieved}

        context_parts: list[str] = []
        sources: list[SourceReference] = []

        for segment in ordered_segments:
            doc = segment.document
            doc_title = doc.Title if doc else "Unknown"

            context_parts.append(
                f"[Source: {doc_title}, Chunk {segment.ChunkIndex}]\n{segment.Content}"
            )

            rrf_result = rrf_map.get(segment.VectorStoreId)
            sources.append(
                SourceReference(
                    document_id=str(segment.DocumentId),
                    document_title=doc_title,
                    chunk_index=segment.ChunkIndex,
                    content_preview=segment.Content[:200],
                    relevance_score=_display_score(rrf_result),
                )
            )

        context = "\n\n---\n\n".join(context_parts)

        # 5. Generate response via LLM (fallback to raw chunks if LLM unavailable)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context documents:\n\n{context}\n\nQuestion: {question}",
            },
        ]

        try:
            answer = await self.llm_service.generate(messages)
        except Exception as llm_err:
            logger.warning(
                "LLM unavailable, returning raw retrieval results",
                error=str(llm_err)[:200],
            )
            # Build a readable fallback from the retrieved chunks
            fallback_parts = []
            for src in sources[:5]:
                fallback_parts.append(
                    f"**{src.document_title}** (Chunk {src.chunk_index}):\n{src.content_preview}..."
                )
            answer = (
                "*LLM is temporarily unavailable (rate limit or error). "
                "Here are the most relevant document excerpts:*\n\n"
                + "\n\n---\n\n".join(fallback_parts)
            )

        logger.info(
            "RAG pipeline complete",
            question_preview=question[:100],
            sources_count=len(sources),
        )

        return RAGResponse(
            answer=answer,
            sources=sources,
            segments=ordered_segments,
        )
