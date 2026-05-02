import base64
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.documents import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentStatusResponse,
)
from app.config import Settings
from app.core.exceptions import DocumentNotFoundError, DocumentProcessingError
from app.db.models import TextSegment
from app.db.repositories import DocumentRepository, TextSegmentRepository
from app.dependencies import (
    get_bm25_store,
    get_db_session,
    get_document_processor,
    get_document_repo,
    get_embedding_service,
    get_settings,
    get_text_segment_repo,
    get_vector_store,
)
from app.rag.bm25_store import BM25Store
from app.rag.vector_store import FAISSVectorStore
from app.services.chunking import RegulatoryChunker
from app.services.document_processor import DocumentProcessor
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    session: AsyncSession = Depends(get_db_session),
    doc_repo: DocumentRepository = Depends(get_document_repo),
    segment_repo: TextSegmentRepository = Depends(get_text_segment_repo),
    processor: DocumentProcessor = Depends(get_document_processor),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    bm25_store: BM25Store = Depends(get_bm25_store),
    settings: Settings = Depends(get_settings),
) -> DocumentIngestResponse:
    """Ingest a document: extract text, chunk, embed, and index.

    The Document record must already exist in SQL (created by .NET backend).
    This endpoint creates TextSegment records and indexes into FAISS + BM25.
    """
    # Verify document exists
    document = await doc_repo.get_by_id(request.document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {request.document_id} not found in database")

    # Decode base64 content
    try:
        content_bytes = base64.b64decode(request.content)
    except Exception as e:
        raise DocumentProcessingError(f"Invalid base64 content: {e}") from e

    # Extract text
    text = processor.extract_text(content_bytes, request.file_type)

    # Chunk text — RegulatoryChunker emits hierarchy-aware chunks with
    # a section breadcrumb attached. The breadcrumb is prepended at index
    # time so semantic + lexical retrieval see section context, but the
    # raw `Content` we persist to SQL stays clean for display.
    chunker = RegulatoryChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        document_title=document.Title,
    )
    chunks = chunker.chunk_text(text)

    if not chunks:
        raise DocumentProcessingError("No text chunks produced from document")

    # Texts that go into the FAISS + BM25 indexes carry the breadcrumb;
    # texts that go into SQL do not.
    indexing_texts = [c.for_indexing() for c in chunks]
    embeddings = await embedding_service.embed_texts(indexing_texts)

    # Create TextSegment records and assign VectorStoreIds
    segments: list[TextSegment] = []
    vector_store_ids: list[str] = []

    for chunk in chunks:
        vs_id = str(uuid.uuid4())
        vector_store_ids.append(vs_id)

        segment = TextSegment(
            Id=uuid.uuid4(),
            DocumentId=request.document_id,
            Content=chunk.content,
            ChunkIndex=chunk.chunk_index,
            VectorStoreId=vs_id,
            CreatedAt=datetime.utcnow(),
        )
        segments.append(segment)

    # Save segments to DB
    await segment_repo.bulk_create(segments)

    # Add to FAISS index
    vector_store.add_vectors(embeddings, vector_store_ids)
    vector_store.save()

    # Add to BM25 index — breadcrumb-prefixed text so section keywords
    # ("Article 4", "4.2.1", "Échantillonnage") are searchable.
    bm25_store.add_documents(indexing_texts, vector_store_ids)
    bm25_store.save(f"{settings.faiss_index_path}/bm25_index.pkl")

    await session.commit()

    logger.info(
        "Document ingested",
        document_id=str(request.document_id),
        segments=len(segments),
    )

    return DocumentIngestResponse(
        document_id=request.document_id,
        segments_created=len(segments),
        vectors_indexed=len(embeddings),
        status="success",
    )


@router.delete("/{document_id}")
async def delete_document_index(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    segment_repo: TextSegmentRepository = Depends(get_text_segment_repo),
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    bm25_store: BM25Store = Depends(get_bm25_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Remove document segments from indexes and database (for re-indexing)."""
    vector_store_ids = await segment_repo.delete_by_document_id(document_id)

    if vector_store_ids:
        vector_store.remove_vectors(vector_store_ids)
        vector_store.save()
        bm25_store.remove_documents(set(vector_store_ids))
        bm25_store.save(f"{settings.faiss_index_path}/bm25_index.pkl")

    await session.commit()

    return {
        "document_id": str(document_id),
        "segments_removed": len(vector_store_ids),
        "status": "success",
    }


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    doc_repo: DocumentRepository = Depends(get_document_repo),
    segment_repo: TextSegmentRepository = Depends(get_text_segment_repo),
) -> DocumentStatusResponse:
    """Check ingestion status for a document."""
    document = await doc_repo.get_by_id(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    segments = await segment_repo.get_by_document_id(document_id)
    indexed = all(s.VectorStoreId is not None for s in segments) and len(segments) > 0

    return DocumentStatusResponse(
        document_id=document_id,
        title=document.Title,
        segment_count=len(segments),
        indexed=indexed,
    )
