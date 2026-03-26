"""API integration tests using TestClient."""

import pytest


class TestHealthEndpoint:
    def test_health_no_auth_required(self, test_client):
        response = test_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "faiss_index_size" in data
        assert "bm25_index_size" in data


class TestAuthMiddleware:
    def test_missing_api_key_returns_401(self, test_client):
        response = test_client.post("/api/search", json={"query": "test"})
        assert response.status_code == 401

    def test_invalid_api_key_returns_401(self, test_client):
        response = test_client.post(
            "/api/search",
            json={"query": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_valid_api_key_passes_auth(self, test_client, auth_headers):
        # Search endpoint with valid key — should pass auth
        # (may fail on DB but auth should pass)
        response = test_client.post(
            "/api/search",
            json={"query": "test", "top_k": 5},
            headers=auth_headers,
        )
        # If DB is not available, we might get 500, but NOT 401
        assert response.status_code != 401


class TestSearchEndpoint:
    def test_search_requires_query(self, test_client, auth_headers):
        response = test_client.post(
            "/api/search",
            json={"top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error

    def test_search_validates_top_k(self, test_client, auth_headers):
        response = test_client.post(
            "/api/search",
            json={"query": "test", "top_k": 0},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_search_validates_top_k_max(self, test_client, auth_headers):
        response = test_client.post(
            "/api/search",
            json={"query": "test", "top_k": 100},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAnalysisEndpoint:
    def test_analysis_status_not_found(self, test_client, auth_headers):
        response = test_client.get(
            "/api/analyze/00000000-0000-0000-0000-000000000000/status",
            headers=auth_headers,
        )
        # Should fail with 404 or 500 (DB not available in test)
        assert response.status_code in (404, 500)

    def test_analysis_requires_document_id(self, test_client, auth_headers):
        response = test_client.post(
            "/api/analyze",
            json={
                "document_content": "dGVzdA==",
                "file_type": "txt",
                "title": "Test",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestDocumentsEndpoint:
    def test_ingest_requires_document_id(self, test_client, auth_headers):
        response = test_client.post(
            "/api/documents/ingest",
            json={
                "content": "dGVzdA==",
                "file_type": "txt",
                "title": "Test",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_document_status_requires_auth(self, test_client):
        response = test_client.get(
            "/api/documents/00000000-0000-0000-0000-000000000000/status"
        )
        assert response.status_code == 401
