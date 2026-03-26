import os
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Set required env vars before importing app modules
os.environ.setdefault("AI_SERVICE_API_KEY", "test-api-key")
os.environ.setdefault("AI_SERVICE_DATABASE_CONNECTION_STRING", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("AI_SERVICE_LLM_PROVIDER", "azure")
os.environ.setdefault("AI_SERVICE_AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AI_SERVICE_AZURE_OPENAI_API_KEY", "test-openai-key")


@pytest.fixture
def api_key() -> str:
    return "test-api-key"


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.size = 0
    store.search.return_value = []
    store.add_vectors.return_value = None
    store.save.return_value = None
    store.load.return_value = None
    store.remove_vectors.return_value = None
    return store


@pytest.fixture
def mock_bm25_store():
    store = MagicMock()
    store.size = 0
    store.search.return_value = []
    store.add_documents.return_value = None
    store.save.return_value = None
    store.load.return_value = None
    store.remove_documents.return_value = None
    return store


@pytest.fixture
def mock_embedding_model():
    model = MagicMock()
    model.encode.return_value = np.zeros((1, 384), dtype=np.float32)
    return model


@pytest.fixture
def mock_embedding_service():
    service = MagicMock()
    service.embed_query = AsyncMock(return_value=np.zeros(384, dtype=np.float32))
    service.embed_texts = AsyncMock(
        return_value=[np.zeros(384, dtype=np.float32)]
    )
    return service


@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.generate = AsyncMock(return_value="Test LLM response")
    service.generate_structured = AsyncMock()
    return service


@pytest.fixture
def test_client(mock_vector_store, mock_bm25_store, mock_embedding_model):
    """Create a test client with mocked dependencies."""
    with patch("app.main.FAISSVectorStore", return_value=mock_vector_store), \
         patch("app.main.BM25Store", return_value=mock_bm25_store), \
         patch("app.main.SentenceTransformer", return_value=mock_embedding_model):
        from app.main import app
        app.state.vector_store = mock_vector_store
        app.state.bm25_store = mock_bm25_store
        app.state.embedding_model = mock_embedding_model
        yield TestClient(app)
