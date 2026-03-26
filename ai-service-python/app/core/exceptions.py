from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DocumentProcessingError(Exception):
    def __init__(self, detail: str = "Failed to process document"):
        self.detail = detail


class DocumentNotFoundError(Exception):
    def __init__(self, detail: str = "Document not found"):
        self.detail = detail


class EmbeddingError(Exception):
    def __init__(self, detail: str = "Failed to generate embeddings"):
        self.detail = detail


class RetrievalError(Exception):
    def __init__(self, detail: str = "Failed to retrieve documents"):
        self.detail = detail


class AnalysisError(Exception):
    def __init__(self, detail: str = "Failed to perform compliance analysis"):
        self.detail = detail


class LLMError(Exception):
    def __init__(self, detail: str = "LLM request failed"):
        self.detail = detail


class VectorStoreError(Exception):
    def __init__(self, detail: str = "Vector store operation failed"):
        self.detail = detail


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DocumentNotFoundError)
    async def document_not_found_handler(
        request: Request, exc: DocumentNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail, "error_type": "DocumentNotFoundError"},
        )

    @app.exception_handler(DocumentProcessingError)
    async def document_processing_handler(
        request: Request, exc: DocumentProcessingError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.detail, "error_type": "DocumentProcessingError"},
        )

    @app.exception_handler(EmbeddingError)
    async def embedding_handler(
        request: Request, exc: EmbeddingError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": exc.detail, "error_type": "EmbeddingError"},
        )

    @app.exception_handler(RetrievalError)
    async def retrieval_handler(
        request: Request, exc: RetrievalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.detail, "error_type": "RetrievalError"},
        )

    @app.exception_handler(AnalysisError)
    async def analysis_handler(
        request: Request, exc: AnalysisError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.detail, "error_type": "AnalysisError"},
        )

    @app.exception_handler(LLMError)
    async def llm_handler(request: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": exc.detail, "error_type": "LLMError"},
        )

    @app.exception_handler(VectorStoreError)
    async def vector_store_handler(
        request: Request, exc: VectorStoreError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.detail, "error_type": "VectorStoreError"},
        )
