import structlog
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.security import verify_api_key
from app.rag.bm25_store import BM25Store
from app.rag.reranker import CrossEncoderReranker
from app.rag.vector_store import FAISSVectorStore

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logger.info(
        "Starting AI service",
        faiss_path=settings.faiss_index_path,
        embedding_model=settings.embedding_model_name,
    )

    # Load embedding model (local, ~80MB download on first run)
    embedding_model = SentenceTransformer(settings.embedding_model_name)
    app.state.embedding_model = embedding_model
    logger.info("Embedding model loaded", model=settings.embedding_model_name)

    vector_store = FAISSVectorStore(
        index_path=settings.faiss_index_path,
        dimensions=settings.embedding_dimensions,
    )
    vector_store.load()
    app.state.vector_store = vector_store

    bm25_store = BM25Store()
    bm25_store.load(f"{settings.faiss_index_path}/bm25_index.pkl")
    app.state.bm25_store = bm25_store

    logger.info(
        "Indexes loaded",
        faiss_size=vector_store.size,
        bm25_size=bm25_store.size,
    )

    # Cross-encoder reranker (Phase 1). Multilingual MiniLM (~120MB) — pre-baked
    # in the Docker image so cold start doesn't hit HuggingFace.
    if settings.enable_reranker:
        app.state.reranker = CrossEncoderReranker.load(
            settings.reranker_model,
            max_length=settings.reranker_max_length,
        )
    else:
        app.state.reranker = None
        logger.info("Reranker disabled by config")

    yield

    # Shutdown
    logger.info("Shutting down AI service, saving indexes")
    vector_store.save()
    bm25_store.save(f"{settings.faiss_index_path}/bm25_index.pkl")


app = FastAPI(
    title="Sothema AI Compliance Service",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_exception_handlers(app)

# Import and register routers
from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.documents import router as documents_router  # noqa: E402
from app.api.routes.search import router as search_router  # noqa: E402
from app.api.routes.analysis import router as analysis_router  # noqa: E402

app.include_router(health_router)
app.include_router(documents_router, dependencies=[Depends(verify_api_key)])
app.include_router(search_router, dependencies=[Depends(verify_api_key)])
app.include_router(analysis_router, dependencies=[Depends(verify_api_key)])
