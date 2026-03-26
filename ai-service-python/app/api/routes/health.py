from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(request: Request) -> dict:
    vector_store = request.app.state.vector_store
    bm25_store = request.app.state.bm25_store

    return {
        "status": "healthy",
        "service": "sothema-ai-compliance",
        "faiss_index_size": vector_store.size,
        "bm25_index_size": bm25_store.size,
    }
