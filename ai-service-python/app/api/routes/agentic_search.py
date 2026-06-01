"""Agentic RAG endpoint — powers the Deep Analysis mode."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agentic_rag.budget import AgentBudget
from app.agents.agentic_rag.nodes import RunContext
from app.api.schemas.agentic_search import (
    AgenticSearchRequest,
    AgenticSearchResponse,
    CitationDTO,
    StepLogDTO,
)
from app.api.schemas.search import SearchResult
from app.config import Settings
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
    get_reranker,
    get_settings,
    get_text_segment_repo,
)
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import CrossEncoderReranker
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/agentic-search", tags=["agentic-search"])


@router.post("", response_model=AgenticSearchResponse)
async def agentic_search(
    request: AgenticSearchRequest,
    session: AsyncSession = Depends(get_db_session),
    llm_service: LLMService = Depends(get_llm_service),
    hybrid_retriever: HybridRetriever = Depends(get_hybrid_retriever),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    segment_repo: TextSegmentRepository = Depends(get_text_segment_repo),
    reranker: CrossEncoderReranker | None = Depends(get_reranker),
    ai_request_repo: AiRequestRepository = Depends(get_ai_request_repo),
    ai_request_segment_repo: AiRequestSegmentRepository = Depends(get_ai_request_segment_repo),
    s: Settings = Depends(get_settings),
) -> AgenticSearchResponse:
    """Deep Analysis: LangGraph agent with plan / retrieve / reflect / generate / verify."""

    ctx = RunContext(
        llm=llm_service,
        hybrid_retriever=hybrid_retriever,
        embedding_service=embedding_service,
        segment_repo=segment_repo,
        reranker=reranker,
        reranker_fetch_multiplier=s.reranker_fetch_multiplier,
        groundedness_threshold=s.agent_groundedness_threshold,
    )

    # Graph closures bind to a per-request RunContext (DB-session-scoped
    # segment_repo). LangGraph compile is structural and cheap, so we build per
    # request. If profile data ever shows this matters, swap to a process-level
    # compiled graph with a context-var that injects the per-request collaborators.
    from app.agents.agentic_rag.graph import build_agentic_rag_graph

    compiled = build_agentic_rag_graph(ctx)

    initial_state = {
        "original_query": request.query,
        "top_k": request.top_k,
        "iterations": 0,
        "budget": AgentBudget(
            max_iterations=request.max_iterations,
            max_total_llm_calls=s.agent_max_llm_calls,
            max_wall_clock_ms=s.agent_max_wall_clock_ms,
        ),
        "trace": [],
        "sub_queries": [],
        "retrieved": [],
        "segments_by_id": {},
        "generate_retries": 0,
    }

    final_state = await compiled.ainvoke(initial_state)

    # ─── Project the agent's state into the API response ─────────────────────

    retrieved = final_state.get("retrieved", [])
    segments_by_id = final_state.get("segments_by_id", {})
    top_k = request.top_k

    results: list[SearchResult] = []
    for r in retrieved[:top_k]:
        seg = segments_by_id.get(r.vector_store_id)
        if seg is None:
            continue
        doc = seg.document
        results.append(
            SearchResult(
                document_id=uuid.UUID(str(seg.DocumentId)),
                document_title=(doc.Title if doc else "Unknown"),
                segment_content=(seg.Content or "")[:200],
                chunk_index=seg.ChunkIndex,
                relevance_score=r.rrf_score,
                vector_store_id=seg.VectorStoreId or "",
            )
        )

    citations_out = [
        CitationDTO(
            source_index=c.source_index,
            document_id=uuid.UUID(c.document_id),
            document_title=c.document_title,
            chunk_index=c.chunk_index,
            vector_store_id=c.vector_store_id,
        )
        for c in final_state.get("citations", [])
    ]

    trace_out = [
        StepLogDTO(
            step=t.step, iteration=t.iteration, elapsed_ms=t.elapsed_ms, detail=t.detail
        )
        for t in final_state.get("trace", [])
    ]

    budget: AgentBudget = final_state.get("budget") or AgentBudget()
    answer = final_state.get("answer", "")
    sub_queries = final_state.get("sub_queries", [])

    # ─── Audit trail ─────────────────────────────────────────────────────────

    ai_request = AiRequest(
        Id=uuid.uuid4(),
        Question=request.query,
        Response=answer,
        CreatedAt=datetime.utcnow(),
    )
    await ai_request_repo.create(ai_request)

    ai_segments = []
    for r in retrieved[:top_k]:
        seg = segments_by_id.get(r.vector_store_id)
        if seg is None:
            continue
        ai_segments.append(
            AiRequestSegment(
                AiRequestId=ai_request.Id,
                TextSegmentId=seg.Id,
                RelevanceScore=r.rrf_score,
            )
        )
    if ai_segments:
        await ai_request_segment_repo.bulk_create(ai_segments)
    await session.commit()

    logger.info(
        "Agentic search complete",
        query_preview=request.query[:100],
        iterations=final_state.get("iterations", 0),
        llm_calls=budget.llm_calls_made,
        elapsed_ms=budget.elapsed_ms(),
        groundedness=final_state.get("groundedness_score", 0.0),
        low_confidence=final_state.get("low_confidence", False),
        citations=len(citations_out),
        results=len(results),
    )

    return AgenticSearchResponse(
        query=request.query,
        answer=answer,
        results=results,
        total_results=len(results),
        citations=citations_out,
        groundedness_score=float(final_state.get("groundedness_score", 0.0)),
        low_confidence=bool(final_state.get("low_confidence", False)),
        verification_error=final_state.get("verification_error"),
        iterations=int(final_state.get("iterations", 0)),
        sub_queries=list(sub_queries),
        trace=trace_out,
        llm_calls=budget.llm_calls_made,
        elapsed_ms=budget.elapsed_ms(),
    )
