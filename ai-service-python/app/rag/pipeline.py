from dataclasses import dataclass

import structlog

from app.db.models import TextSegment
from app.db.repositories import TextSegmentRepository
from app.rag.hybrid_retriever import HybridRetriever, RetrievedSegment
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an AI compliance assistant for pharmaceutical regulatory documents.
Answer the user's question based ONLY on the provided context documents.
If the context does not contain enough information to answer, say so clearly.
Always reference which source documents support your answer."""


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
    ):
        self.hybrid_retriever = hybrid_retriever
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.segment_repo = segment_repo

    async def retrieve_only(self, question: str, top_k: int = 10) -> RAGResponse:
        """Hybrid retrieval without LLM — fast, free, fully transparent.
        Same shape as `query()` but `answer` is empty."""

        query_embedding = await self.embedding_service.embed_query(question)
        retrieved: list[RetrievedSegment] = await self.hybrid_retriever.retrieve(
            query=question,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not retrieved:
            return RAGResponse(answer="", sources=[], segments=[])

        vector_store_ids = [r.vector_store_id for r in retrieved]
        segments = await self.segment_repo.get_by_vector_store_ids(vector_store_ids)
        segment_map = {s.VectorStoreId: s for s in segments if s.VectorStoreId}
        rrf_map = {r.vector_store_id: r for r in retrieved}

        sources: list[SourceReference] = []
        ordered_segments: list[TextSegment] = []
        for vs_id in vector_store_ids:
            segment = segment_map.get(vs_id)
            if segment is None:
                continue
            ordered_segments.append(segment)
            doc = segment.document
            doc_title = doc.Title if doc else "Unknown"
            rrf_result = rrf_map.get(vs_id)
            sources.append(
                SourceReference(
                    document_id=str(segment.DocumentId),
                    document_title=doc_title,
                    chunk_index=segment.ChunkIndex,
                    content_preview=segment.Content[:500],
                    relevance_score=rrf_result.rrf_score if rrf_result else 0.0,
                )
            )

        logger.info(
            "Retrieval-only search complete",
            question_preview=question[:100],
            sources_count=len(sources),
        )
        return RAGResponse(answer="", sources=sources, segments=ordered_segments)

    async def query(self, question: str, top_k: int = 10) -> RAGResponse:
        # 1. Embed the question
        query_embedding = await self.embedding_service.embed_query(question)

        # 2. Retrieve segments via hybrid retriever
        retrieved: list[RetrievedSegment] = await self.hybrid_retriever.retrieve(
            query=question,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not retrieved:
            return RAGResponse(
                answer="No relevant documents found for your query.",
                sources=[],
                segments=[],
            )

        # 3. Fetch full TextSegment records from DB
        vector_store_ids = [r.vector_store_id for r in retrieved]
        segments = await self.segment_repo.get_by_vector_store_ids(vector_store_ids)

        # Map by VectorStoreId for easy lookup
        segment_map = {s.VectorStoreId: s for s in segments if s.VectorStoreId}
        rrf_map = {r.vector_store_id: r for r in retrieved}

        # 4. Build context prompt
        context_parts = []
        sources = []
        ordered_segments = []

        for vs_id in vector_store_ids:
            segment = segment_map.get(vs_id)
            if segment is None:
                continue

            ordered_segments.append(segment)
            doc = segment.document
            doc_title = doc.Title if doc else "Unknown"

            context_parts.append(
                f"[Source: {doc_title}, Chunk {segment.ChunkIndex}]\n{segment.Content}"
            )

            rrf_result = rrf_map.get(vs_id)
            sources.append(
                SourceReference(
                    document_id=str(segment.DocumentId),
                    document_title=doc_title,
                    chunk_index=segment.ChunkIndex,
                    content_preview=segment.Content[:200],
                    relevance_score=rrf_result.rrf_score if rrf_result else 0.0,
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
