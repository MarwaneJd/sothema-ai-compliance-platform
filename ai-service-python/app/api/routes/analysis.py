"""Analysis endpoints — compliance analysis via LangGraph agent pipeline."""

import asyncio
import base64
import json
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.audit import AuditAgent
from app.agents.compliance_scoring import ComplianceScoringAgent
from app.agents.content_analysis import ContentAnalysisAgent
from app.agents.document_retrieval import DocumentRetrievalAgent
from app.agents.explanation import ExplanationAgent
from app.agents.graph import run_compliance_pipeline
from app.agents.regulatory_compliance import RegulatoryComplianceAgent
from app.api.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatusResponse,
)
from app.config import Settings
from app.db.models import ComplianceAnalysis
from app.db.repositories import (
    AuditLogRepository,
    ComplianceAnalysisRepository,
    TextSegmentRepository,
)
from app.db.session import async_session_factory
from app.dependencies import (
    get_bm25_store,
    get_compliance_analysis_repo,
    get_db_session,
    get_embedding_service,
    get_settings,
    get_vector_store,
)
from app.rag.bm25_store import BM25Store
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.vector_store import FAISSVectorStore
from app.db.models import TextSegment
from app.services.chunking import TextChunker
from app.services.document_processor import DocumentProcessor
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService

logger = structlog.get_logger()

# AnalysisStatus enum values matching C#
STATUS_PENDING = 0
STATUS_PROCESSING = 1
STATUS_COMPLETED = 2
STATUS_FAILED = 3

STATUS_NAMES = {0: "pending", 1: "processing", 2: "completed", 3: "failed"}

router = APIRouter(prefix="/api/analyze", tags=["analysis"])


@router.post("", response_model=AnalysisResponse)
async def trigger_analysis(
    request: AnalysisRequest,
    session: AsyncSession = Depends(get_db_session),
    analysis_repo: ComplianceAnalysisRepository = Depends(get_compliance_analysis_repo),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    bm25_store: BM25Store = Depends(get_bm25_store),
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    """Trigger a compliance analysis. Returns immediately with a job_id for polling."""
    # Create ComplianceAnalysis record with Pending status
    analysis = ComplianceAnalysis(
        Id=uuid.uuid4(),
        DocumentId=request.document_id,
        Score=0.0,
        Summary="",
        Details=None,
        Status=STATUS_PENDING,
        AnalyzedAt=datetime.utcnow(),
    )
    await analysis_repo.create(analysis)
    await session.commit()

    job_id = analysis.Id

    # Launch background task
    asyncio.create_task(
        _run_analysis_background(
            job_id=job_id,
            document_id=request.document_id,
            document_content_b64=request.document_content,
            file_type=request.file_type,
            title=request.title,
            embedding_service=embedding_service,
            vector_store=vector_store,
            bm25_store=bm25_store,
            settings=settings,
        )
    )

    logger.info("Analysis triggered", job_id=str(job_id), document_id=str(request.document_id))

    return AnalysisResponse(
        job_id=job_id,
        status="pending",
        message="Compliance analysis started",
    )


@router.get("/{job_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    job_id: uuid.UUID,
    analysis_repo: ComplianceAnalysisRepository = Depends(get_compliance_analysis_repo),
) -> AnalysisStatusResponse:
    """Poll the status of a compliance analysis job."""
    analysis = await analysis_repo.get_by_id(job_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    # Parse details JSON if present
    details_dict = None
    if analysis.Details:
        try:
            details_dict = json.loads(analysis.Details)
        except json.JSONDecodeError:
            details_dict = {"raw": analysis.Details}

    return AnalysisStatusResponse(
        job_id=job_id,
        status=STATUS_NAMES.get(analysis.Status, "unknown"),
        score=analysis.Score if analysis.Status == STATUS_COMPLETED else None,
        summary=analysis.Summary if analysis.Status == STATUS_COMPLETED else None,
        details=details_dict if analysis.Status == STATUS_COMPLETED else None,
        analyzed_at=analysis.AnalyzedAt,
    )


async def _run_analysis_background(
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    document_content_b64: str,
    file_type: str,
    title: str,
    embedding_service: EmbeddingService,
    vector_store: FAISSVectorStore,
    bm25_store: BM25Store,
    settings: Settings,
) -> None:
    """Background task: run the full LangGraph compliance pipeline."""
    async with async_session_factory() as session:
        analysis_repo = ComplianceAnalysisRepository(session)
        audit_repo = AuditLogRepository(session)
        segment_repo = TextSegmentRepository(session)

        try:
            # Update status to Processing
            await analysis_repo.update_status(job_id, STATUS_PROCESSING)
            await session.commit()

            # Extract text from document
            processor = DocumentProcessor()
            content_bytes = base64.b64decode(document_content_b64)
            document_text = processor.extract_text(content_bytes, file_type)

            # --- Ingest into RAG indexes (skip if already indexed) ---
            existing_segments = await segment_repo.get_by_document_id(document_id)
            if not existing_segments:
                try:
                    chunker = TextChunker(
                        chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap,
                    )
                    chunks = chunker.chunk_text(document_text)

                    if chunks:
                        chunk_texts = [c.content for c in chunks]
                        embeddings = await embedding_service.embed_texts(chunk_texts)

                        segments = []
                        vector_store_ids = []
                        for chunk in chunks:
                            vs_id = str(uuid.uuid4())
                            vector_store_ids.append(vs_id)
                            segments.append(TextSegment(
                                Id=uuid.uuid4(),
                                DocumentId=document_id,
                                Content=chunk.content,
                                ChunkIndex=chunk.chunk_index,
                                VectorStoreId=vs_id,
                                CreatedAt=datetime.utcnow(),
                            ))

                        await segment_repo.bulk_create(segments)

                        vector_store.add_vectors(embeddings, vector_store_ids)
                        vector_store.save()

                        bm25_store.add_documents(chunk_texts, vector_store_ids)
                        bm25_store.save(f"{settings.faiss_index_path}/bm25_index.pkl")

                        await session.commit()
                        logger.info(
                            "Document indexed for RAG",
                            document_id=str(document_id),
                            segments=len(segments),
                        )
                except Exception as ingest_err:
                    logger.error(
                        "RAG ingestion failed, continuing with analysis",
                        error=str(ingest_err),
                        document_id=str(document_id),
                    )
            else:
                logger.info(
                    "Document already indexed, skipping ingestion",
                    document_id=str(document_id),
                    segments=len(existing_segments),
                )

            # Build agents
            hybrid_retriever = HybridRetriever(
                vector_store=vector_store,
                bm25_store=bm25_store,
                k=settings.rrf_k,
            )
            llm_service = LLMService(settings)

            doc_retrieval = DocumentRetrievalAgent(hybrid_retriever, embedding_service)
            content_analysis = ContentAnalysisAgent(llm_service)
            regulatory = RegulatoryComplianceAgent(llm_service)
            scoring = ComplianceScoringAgent(llm_service)
            explanation = ExplanationAgent(llm_service)
            audit = AuditAgent(audit_repo)

            # Run the pipeline
            final_state = await run_compliance_pipeline(
                job_id=str(job_id),
                document_id=str(document_id),
                document_content=document_text,
                document_title=title,
                doc_retrieval=doc_retrieval,
                content_analysis=content_analysis,
                regulatory=regulatory,
                scoring=scoring,
                explanation=explanation,
                audit=audit,
            )

            # Extract results from final state
            scores = final_state.get("scores", {})
            total_score = float(scores.get("total_score", 0))
            summary = final_state.get("explanation", "")
            details_json = json.dumps(scores)

            # Update ComplianceAnalysis with results
            await analysis_repo.update_status(
                analysis_id=job_id,
                status=STATUS_COMPLETED,
                score=total_score,
                summary=summary,
                details=details_json,
            )
            await session.commit()

            logger.info(
                "Analysis completed",
                job_id=str(job_id),
                score=total_score,
            )

        except Exception as e:
            logger.error("Analysis failed", job_id=str(job_id), error=str(e))
            try:
                await analysis_repo.update_status(
                    analysis_id=job_id,
                    status=STATUS_FAILED,
                    summary=f"Analysis failed: {e}",
                )
                await session.commit()
            except Exception as commit_error:
                logger.error(
                    "Failed to update analysis status to failed",
                    error=str(commit_error),
                )
