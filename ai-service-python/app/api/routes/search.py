"""Search endpoint — hybrid RAG search with LLM answer generation."""

import uuid
from datetime import datetime

import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.db.models import AiRequest, AiRequestSegment
from app.db.repositories import (
    AiRequestRepository,
    AiRequestSegmentRepository,
    TextSegmentRepository,
)
from app.dependencies import (
    get_ai_request_repo,
    get_ai_request_segment_repo,
    get_db_session,
    get_embedding_service,
    get_hybrid_retriever,
    get_llm_service,
    get_text_segment_repo,
)
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.pipeline import RAGPipeline
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    hybrid_retriever: HybridRetriever = Depends(get_hybrid_retriever),
    llm_service: LLMService = Depends(get_llm_service),
    segment_repo: TextSegmentRepository = Depends(get_text_segment_repo),
    ai_request_repo: AiRequestRepository = Depends(get_ai_request_repo),
    ai_request_segment_repo: AiRequestSegmentRepository = Depends(get_ai_request_segment_repo),
) -> SearchResponse:
    """Hybrid RAG search — retrieves relevant chunks then generates an LLM answer."""

    # 1. Run the full RAG pipeline (retrieve + LLM answer)
    rag = RAGPipeline(
        hybrid_retriever=hybrid_retriever,
        embedding_service=embedding_service,
        llm_service=llm_service,
        segment_repo=segment_repo,
    )

    rag_response = (
        await rag.query(question=request.query, top_k=request.top_k)
        if request.include_answer
        else await rag.retrieve_only(question=request.query, top_k=request.top_k)
    )

    # 2. Build search results from sources
    results: list[SearchResult] = [
        SearchResult(
            document_id=src.document_id,
            document_title=src.document_title,
            segment_content=src.content_preview,
            chunk_index=src.chunk_index,
            relevance_score=src.relevance_score,
            vector_store_id="",
        )
        for src in rag_response.sources
    ]

    # 3. Audit trail
    ai_request = AiRequest(
        Id=uuid.uuid4(),
        Question=request.query,
        Response=rag_response.answer,
        CreatedAt=datetime.utcnow(),
    )
    await ai_request_repo.create(ai_request)

    ai_segments = [
        AiRequestSegment(
            AiRequestId=ai_request.Id,
            TextSegmentId=seg.Id,
            RelevanceScore=src.relevance_score,
        )
        for seg, src in zip(rag_response.segments, rag_response.sources)
    ]
    if ai_segments:
        await ai_request_segment_repo.bulk_create(ai_segments)

    await session.commit()

    logger.info(
        "RAG search complete",
        query_preview=request.query[:100],
        results_count=len(results),
        answer_length=len(rag_response.answer),
    )

    return SearchResponse(
        query=request.query,
        answer=rag_response.answer,
        results=results,
        total_results=len(results),
    )
