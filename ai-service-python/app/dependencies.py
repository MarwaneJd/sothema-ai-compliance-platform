from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.db.repositories import (
    AiRequestRepository,
    AiRequestSegmentRepository,
    AuditLogRepository,
    ComplianceAnalysisRepository,
    DocumentRepository,
    TextSegmentRepository,
)
from app.db.session import get_db
from app.rag.bm25_store import BM25Store
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.multi_query import MultiQueryRetriever
from app.rag.query_expander import QueryExpander
from app.rag.reranker import CrossEncoderReranker
from app.rag.vector_store import FAISSVectorStore
from app.services.document_processor import DocumentProcessor
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService


def get_settings() -> Settings:
    return settings


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


# Repositories


def get_document_repo(
    session: AsyncSession = Depends(get_db_session),
) -> DocumentRepository:
    return DocumentRepository(session)


def get_text_segment_repo(
    session: AsyncSession = Depends(get_db_session),
) -> TextSegmentRepository:
    return TextSegmentRepository(session)


def get_compliance_analysis_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ComplianceAnalysisRepository:
    return ComplianceAnalysisRepository(session)


def get_audit_log_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AuditLogRepository:
    return AuditLogRepository(session)


def get_ai_request_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AiRequestRepository:
    return AiRequestRepository(session)


def get_ai_request_segment_repo(
    session: AsyncSession = Depends(get_db_session),
) -> AiRequestSegmentRepository:
    return AiRequestSegmentRepository(session)


# Services


def get_document_processor() -> DocumentProcessor:
    return DocumentProcessor()


def get_embedding_service(
    request: Request,
) -> EmbeddingService:
    return EmbeddingService(request.app.state.embedding_model)


def get_llm_service(
    s: Settings = Depends(get_settings),
) -> LLMService:
    return LLMService(s)


# Singleton stores (loaded at startup, accessed via app.state)


def get_vector_store(request: Request) -> FAISSVectorStore:
    return request.app.state.vector_store


def get_bm25_store(request: Request) -> BM25Store:
    return request.app.state.bm25_store


def get_hybrid_retriever(
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    bm25_store: BM25Store = Depends(get_bm25_store),
    s: Settings = Depends(get_settings),
) -> HybridRetriever:
    return HybridRetriever(
        vector_store=vector_store,
        bm25_store=bm25_store,
        k=s.rrf_k,
    )


def get_reranker(request: Request) -> CrossEncoderReranker | None:
    """Singleton, loaded once at startup. Returns None if disabled."""
    return getattr(request.app.state, "reranker", None)


def get_query_expander(request: Request) -> QueryExpander | None:
    """Singleton, lazily initialized on first use. Returns None if disabled."""
    s = settings
    if not s.enable_multi_query:
        return None
    expander = getattr(request.app.state, "query_expander", None)
    if expander is None:
        llm = LLMService(s)
        expander = QueryExpander(
            llm_service=llm,
            n=s.multi_query_count,
            timeout_ms=s.query_expansion_timeout_ms,
            cache_size=s.query_expansion_cache_size,
        )
        request.app.state.query_expander = expander
    return expander


def get_multi_query_retriever(
    request: Request,
    hybrid_retriever: HybridRetriever = Depends(get_hybrid_retriever),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    s: Settings = Depends(get_settings),
) -> MultiQueryRetriever | None:
    """Returns None when multi-query is disabled — caller falls back to hybrid_retriever."""
    expander = get_query_expander(request)
    if expander is None:
        return None
    return MultiQueryRetriever(
        hybrid_retriever=hybrid_retriever,
        embedding_service=embedding_service,
        query_expander=expander,
        n_expansions=s.multi_query_count,
        rrf_k=s.rrf_k,
    )
