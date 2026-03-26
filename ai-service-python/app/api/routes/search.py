"""Search endpoint — hybrid document search (no agents, direct retrieval)."""

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends
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
    get_text_segment_repo,
)
from app.rag.hybrid_retriever import HybridRetriever
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    hybrid_retriever: HybridRetriever = Depends(get_hybrid_retriever),
    segment_repo: TextSegmentRepository = Depends(get_text_segment_repo),
    ai_request_repo: AiRequestRepository = Depends(get_ai_request_repo),
    ai_request_segment_repo: AiRequestSegmentRepository = Depends(get_ai_request_segment_repo),
) -> SearchResponse:
    """Hybrid document search — combines vector and BM25 retrieval with RRF fusion."""
    # 1. Embed the query
    query_embedding = await embedding_service.embed_query(request.query)

    # 2. Hybrid retrieve
    retrieved = await hybrid_retriever.retrieve(
        query=request.query,
        query_embedding=query_embedding,
        top_k=request.top_k,
    )

    if not retrieved:
        return SearchResponse(query=request.query, results=[], total_results=0)

    # 3. Fetch TextSegment records from DB
    vector_store_ids = [r.vector_store_id for r in retrieved]
    segments = await segment_repo.get_by_vector_store_ids(vector_store_ids)

    segment_map = {s.VectorStoreId: s for s in segments if s.VectorStoreId}
    rrf_map = {r.vector_store_id: r for r in retrieved}

    # 4. Build results
    results: list[SearchResult] = []
    matched_segments = []

    for vs_id in vector_store_ids:
        segment = segment_map.get(vs_id)
        if segment is None:
            continue

        matched_segments.append(segment)
        doc = segment.document
        rrf = rrf_map[vs_id]

        results.append(
            SearchResult(
                document_id=segment.DocumentId,
                document_title=doc.Title if doc else "Unknown",
                segment_content=segment.Content,
                chunk_index=segment.ChunkIndex,
                relevance_score=rrf.rrf_score,
                vector_store_id=vs_id,
            )
        )

    # 5. Create AiRequest + AiRequestSegment records for audit trail
    ai_request = AiRequest(
        Id=uuid.uuid4(),
        Question=request.query,
        CreatedAt=datetime.utcnow(),
    )
    await ai_request_repo.create(ai_request)

    ai_segments = [
        AiRequestSegment(
            AiRequestId=ai_request.Id,
            TextSegmentId=segment.Id,
            RelevanceScore=rrf_map.get(segment.VectorStoreId, None)
            and rrf_map[segment.VectorStoreId].rrf_score,
        )
        for segment in matched_segments
        if segment.VectorStoreId
    ]
    if ai_segments:
        await ai_request_segment_repo.bulk_create(ai_segments)

    await session.commit()

    logger.info(
        "Search complete",
        query_preview=request.query[:100],
        results_count=len(results),
    )

    return SearchResponse(
        query=request.query,
        results=results,
        total_results=len(results),
    )
