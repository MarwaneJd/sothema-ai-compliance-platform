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
