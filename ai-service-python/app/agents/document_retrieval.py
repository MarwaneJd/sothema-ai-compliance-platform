"""Document Retrieval Agent — uses hybrid retriever to find relevant segments."""

import structlog

from app.agents.state import ComplianceState
from app.rag.hybrid_retriever import HybridRetriever
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()


class DocumentRetrievalAgent:
    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        embedding_service: EmbeddingService,
    ):
        self.hybrid_retriever = hybrid_retriever
        self.embedding_service = embedding_service

    async def run(self, state: ComplianceState) -> dict:
        """Retrieve relevant document segments using hybrid search."""
        logger.info("Document retrieval agent started", job_id=state.get("job_id"))

        document_content = state.get("document_content", "")
        document_title = state.get("document_title", "")

        # Use title + first 500 chars as the retrieval query
        query = f"{document_title}\n{document_content[:500]}"

        try:
            query_embedding = await self.embedding_service.embed_query(query)
            results = await self.hybrid_retriever.retrieve(
                query=query,
                query_embedding=query_embedding,
                top_k=10,
            )

            segments = [
                {
                    "vector_store_id": r.vector_store_id,
                    "rrf_score": r.rrf_score,
                    "vector_rank": r.vector_rank,
                    "bm25_rank": r.bm25_rank,
                }
                for r in results
            ]

            logger.info(
                "Document retrieval complete",
                segments_found=len(segments),
                job_id=state.get("job_id"),
            )

            return {
                "retrieved_segments": segments,
                "current_agent": "document_retrieval",
            }

        except Exception as e:
            logger.error("Document retrieval failed", error=str(e))
            return {
                "retrieved_segments": [],
                "current_agent": "document_retrieval",
                "error": f"Document retrieval failed: {e}",
            }
