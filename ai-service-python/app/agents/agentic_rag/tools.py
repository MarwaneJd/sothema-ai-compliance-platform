"""Agent tools — thin wrappers over existing retrieval/repo primitives.

These are plain async functions, NOT LangChain `Tool` objects. The LangGraph
nodes invoke them deterministically (no LLM tool-call routing), so the simpler
abstraction wins.

Note on rerank semantics: `hybrid_search` here intentionally does NOT call the
multi-query expander. The agent's `plan` node already decomposes the user
question into focused sub-queries; running multi-query rephrasing on top would
double-expand and burn budget for little additional recall.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog

from app.db.models import TextSegment
from app.db.repositories import DocumentRepository, TextSegmentRepository
from app.rag.hybrid_retriever import HybridRetriever, RetrievedSegment
from app.rag.reranker import CrossEncoderReranker
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()


@dataclass
class HybridSearchResult:
    retrieved: list[RetrievedSegment]
    segments: list[TextSegment]


async def hybrid_search(
    query: str,
    top_k: int,
    *,
    hybrid_retriever: HybridRetriever,
    embedding_service: EmbeddingService,
    segment_repo: TextSegmentRepository,
    reranker: CrossEncoderReranker | None,
    reranker_fetch_multiplier: int = 4,
) -> HybridSearchResult:
    """Embed → FAISS+BM25+RRF → (optional) cross-encoder rerank. Returns ranked top_k.

    Lifts the same logic out of `RAGPipeline._retrieve_and_rerank` so the agent
    doesn't have to instantiate a full pipeline per call. Kept deliberately
    free of multi-query expansion (see module docstring).
    """
    fetch_k = top_k * reranker_fetch_multiplier if reranker else top_k
    query_embedding = await embedding_service.embed_query(query)
    candidates = await hybrid_retriever.retrieve(
        query=query, query_embedding=query_embedding, top_k=fetch_k
    )
    if not candidates:
        return HybridSearchResult(retrieved=[], segments=[])

    ids = [c.vector_store_id for c in candidates]
    segments = await segment_repo.get_by_vector_store_ids(ids)
    seg_by_id = {s.VectorStoreId: s for s in segments if s.VectorStoreId}

    if reranker is None:
        ordered_segments = [seg_by_id[v] for v in ids if v in seg_by_id][:top_k]
        ordered_retrieved = [c for c in candidates if c.vector_store_id in seg_by_id][:top_k]
        return HybridSearchResult(retrieved=ordered_retrieved, segments=ordered_segments)

    aligned_candidates: list[RetrievedSegment] = []
    aligned_texts: list[str] = []
    for c in candidates:
        seg = seg_by_id.get(c.vector_store_id)
        if seg is None:
            continue
        aligned_candidates.append(c)
        aligned_texts.append(seg.Content)

    reranked = await reranker.rerank(
        query=query,
        candidates=aligned_candidates,
        candidate_texts=aligned_texts,
        top_n=top_k,
    )
    rrf_by_id = {c.vector_store_id: c for c in candidates}
    final_retrieved: list[RetrievedSegment] = []
    final_segments: list[TextSegment] = []
    for rr in reranked:
        seg = seg_by_id.get(rr.vector_store_id)
        base = rrf_by_id.get(rr.vector_store_id)
        if seg is None or base is None:
            continue
        final_retrieved.append(base)
        final_segments.append(seg)

    return HybridSearchResult(retrieved=final_retrieved, segments=final_segments)


async def get_neighbors(
    vector_store_id: str,
    *,
    segment_repo: TextSegmentRepository,
    before: int = 1,
    after: int = 1,
) -> list[TextSegment]:
    """Fetch adjacent chunks in the same document (inclusive of the anchor)."""
    return await segment_repo.get_neighbors_by_vector_store_id(
        vector_store_id=vector_store_id, before=before, after=after
    )


@dataclass
class DocumentMetadata:
    document_id: str
    title: str
    file_type: str
    chunk_count: int


async def lookup_document(
    document_id: uuid.UUID,
    *,
    document_repo: DocumentRepository,
    segment_repo: TextSegmentRepository,
) -> DocumentMetadata | None:
    """Lightweight metadata for the planner — title, file type, chunk count."""
    doc = await document_repo.get_by_id(document_id)
    if doc is None:
        return None
    segments = await segment_repo.get_by_document_id(document_id)
    return DocumentMetadata(
        document_id=str(doc.Id),
        title=doc.Title or "",
        file_type=doc.FileType or "",
        chunk_count=len(segments),
    )
