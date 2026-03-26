from unittest.mock import MagicMock

import numpy as np
import pytest

from app.rag.hybrid_retriever import HybridRetriever


class TestHybridRetriever:
    def setup_method(self):
        self.vector_store = MagicMock()
        self.bm25_store = MagicMock()
        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            bm25_store=self.bm25_store,
            k=60,
        )

    @pytest.mark.asyncio
    async def test_empty_results(self):
        self.vector_store.search.return_value = []
        self.bm25_store.search.return_value = []

        query_embedding = np.zeros(384, dtype=np.float32)
        results = await self.retriever.retrieve("test query", query_embedding, top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_vector_only_results(self):
        self.vector_store.search.return_value = [
            ("vs_1", 0.95),
            ("vs_2", 0.85),
        ]
        self.bm25_store.search.return_value = []

        query_embedding = np.zeros(384, dtype=np.float32)
        results = await self.retriever.retrieve("test query", query_embedding, top_k=5)

        assert len(results) == 2
        assert results[0].vector_store_id == "vs_1"
        assert results[0].vector_rank == 1
        assert results[0].bm25_rank is None

    @pytest.mark.asyncio
    async def test_bm25_only_results(self):
        self.vector_store.search.return_value = []
        self.bm25_store.search.return_value = [
            ("vs_a", 5.0),
            ("vs_b", 3.0),
        ]

        query_embedding = np.zeros(384, dtype=np.float32)
        results = await self.retriever.retrieve("test query", query_embedding, top_k=5)

        assert len(results) == 2
        assert results[0].vector_store_id == "vs_a"
        assert results[0].bm25_rank == 1
        assert results[0].vector_rank is None

    @pytest.mark.asyncio
    async def test_rrf_fusion_ranking(self):
        """Documents appearing in both lists should rank higher."""
        self.vector_store.search.return_value = [
            ("vs_both", 0.9),
            ("vs_vector_only", 0.8),
        ]
        self.bm25_store.search.return_value = [
            ("vs_both", 4.0),
            ("vs_bm25_only", 3.0),
        ]

        query_embedding = np.zeros(384, dtype=np.float32)
        results = await self.retriever.retrieve("test query", query_embedding, top_k=5)

        # "vs_both" should be ranked first (appears in both lists)
        assert results[0].vector_store_id == "vs_both"
        assert results[0].vector_rank is not None
        assert results[0].bm25_rank is not None

        # Its RRF score should be higher than single-source results
        assert results[0].rrf_score > results[1].rrf_score

    @pytest.mark.asyncio
    async def test_rrf_score_calculation(self):
        """Verify RRF formula: score = 1/(k+rank_vector) + 1/(k+rank_bm25)."""
        self.vector_store.search.return_value = [("vs_1", 0.9)]
        self.bm25_store.search.return_value = [("vs_1", 4.0)]

        query_embedding = np.zeros(384, dtype=np.float32)
        results = await self.retriever.retrieve("test query", query_embedding, top_k=5)

        expected_score = 1.0 / (60 + 1) + 1.0 / (60 + 1)  # rank=1 in both
        assert abs(results[0].rrf_score - expected_score) < 1e-6

    @pytest.mark.asyncio
    async def test_top_k_limit(self):
        self.vector_store.search.return_value = [
            (f"vs_{i}", 0.9 - i * 0.1) for i in range(10)
        ]
        self.bm25_store.search.return_value = []

        query_embedding = np.zeros(384, dtype=np.float32)
        results = await self.retriever.retrieve("test query", query_embedding, top_k=3)

        assert len(results) == 3
