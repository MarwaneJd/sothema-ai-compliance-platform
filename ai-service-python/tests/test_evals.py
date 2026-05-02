"""Smoke tests for the eval harness — exercise the plumbing (goldset
parsing, ranx wiring, judge JSON handling) without hitting the DB or
the real LLM. The actual goldset numbers depend on labeled data that
ships separately."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.evals.goldset import GoldEntry, load_goldset
from app.evals.judge import score_answer_relevance, score_faithfulness
from app.evals.runner import RetrieverProtocol, evaluate_retrieval


class _FakeRetriever:
    """Returns a hard-coded ranking per query — sufficient to exercise
    the ranx scoring path without running an actual hybrid retriever."""

    def __init__(self, rankings: dict[str, list[str]]):
        self._rankings = rankings

    async def retrieve_ids(self, query: str, top_k: int) -> list[str]:
        return self._rankings.get(query, [])[:top_k]


# Reassure the type checker that _FakeRetriever satisfies the Protocol.
_: RetrieverProtocol = _FakeRetriever({})


class TestGoldsetLoader:
    def test_load_empty_or_missing(self, tmp_path: Path):
        # Missing file → empty list (eval still runnable in CI before labels exist)
        assert load_goldset(tmp_path / "nope.jsonl") == []

    def test_skips_comments_and_blanks(self, tmp_path: Path):
        path = tmp_path / "g.jsonl"
        path.write_text(
            "# a comment\n"
            "\n"
            "   \n"
            '{"id":"q1","query":"Quoi ?","language":"fr","intent":"lookup","relevant_segment_ids":["a"]}\n'
        )
        entries = load_goldset(path)
        assert len(entries) == 1
        assert entries[0].id == "q1"

    def test_required_fields_validated(self, tmp_path: Path):
        path = tmp_path / "g.jsonl"
        path.write_text('{"id":"q1","query":"x","language":"fr"}\n')  # missing intent + ids
        with pytest.raises(ValueError, match="missing required"):
            load_goldset(path)

    def test_bad_intent_rejected(self, tmp_path: Path):
        path = tmp_path / "g.jsonl"
        path.write_text(
            '{"id":"q1","query":"x","language":"fr","intent":"chitchat","relevant_segment_ids":["a"]}\n'
        )
        with pytest.raises(ValueError, match="Bad intent"):
            load_goldset(path)

    def test_duplicate_ids_rejected(self, tmp_path: Path):
        path = tmp_path / "g.jsonl"
        line = '{"id":"q1","query":"x","language":"fr","intent":"lookup","relevant_segment_ids":["a"]}\n'
        path.write_text(line + line)
        with pytest.raises(ValueError, match="duplicate"):
            load_goldset(path)

    def test_invalid_json_pinpoints_line(self, tmp_path: Path):
        path = tmp_path / "g.jsonl"
        path.write_text('{not json}\n')
        with pytest.raises(ValueError, match=":1:"):
            load_goldset(path)

    def test_committed_goldset_parses(self):
        # The repo's actual goldset must always parse — protects against
        # someone editing it into a broken state.
        repo_goldset = Path(__file__).parent.parent / "app" / "evals" / "goldset.jsonl"
        load_goldset(repo_goldset)  # must not raise


class TestRetrievalEval:
    @pytest.mark.asyncio
    async def test_empty_goldset_returns_zero_count(self):
        retriever = _FakeRetriever({})
        out = await evaluate_retrieval([], retriever, top_k=5)
        assert out == {"n_queries": 0}

    @pytest.mark.asyncio
    async def test_perfect_ranking_scores_one(self):
        gold = [
            GoldEntry(
                id="q1",
                query="quelle procédure ?",
                language="fr",
                intent="lookup",
                relevant_segment_ids=("doc-a",),
            )
        ]
        # Doc-a returned first → recall@5=1.0, MRR=1.0, nDCG=1.0
        retriever = _FakeRetriever({"quelle procédure ?": ["doc-a", "doc-b", "doc-c"]})
        out = await evaluate_retrieval(gold, retriever, top_k=5, metrics=("recall@5", "mrr@10"))
        assert out["recall@5"] == pytest.approx(1.0)
        assert out["mrr@10"] == pytest.approx(1.0)
        assert out["n_queries"] == 1

    @pytest.mark.asyncio
    async def test_missed_relevant_scores_zero_recall(self):
        gold = [
            GoldEntry(
                id="q1", query="x", language="fr", intent="lookup",
                relevant_segment_ids=("doc-a",),
            )
        ]
        # doc-a never appears in the ranking
        retriever = _FakeRetriever({"x": ["doc-b", "doc-c"]})
        out = await evaluate_retrieval(gold, retriever, top_k=5, metrics=("recall@5",))
        assert out["recall@5"] == pytest.approx(0.0)


class TestJudge:
    @pytest.mark.asyncio
    async def test_faithfulness_parses_json_score(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(
            return_value=json.dumps(
                {"claims": [{"claim": "x", "supported": True}], "score": 0.9}
            )
        )
        result = await score_faithfulness(
            answer="La qualité est essentielle.", sources=["Doc 1"], llm_service=llm
        )
        assert result.score == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_relevance_clamps_out_of_range_score(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=json.dumps({"score": 1.7}))  # too high
        result = await score_answer_relevance(answer="X", query="Y", llm_service=llm)
        assert result.score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_judge_handles_non_json_gracefully(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value="this is not json at all")
        result = await score_faithfulness(answer="X", sources=["S"], llm_service=llm)
        assert result.score == 0.0
        assert "error" in result.raw

    @pytest.mark.asyncio
    async def test_empty_answer_short_circuits(self):
        llm = AsyncMock()
        result = await score_faithfulness(answer="   ", sources=["S"], llm_service=llm)
        assert result.score == 0.0
        # LLM must not be called when there's nothing to evaluate
        llm.generate.assert_not_called()


class TestBootstrapIndexParser:
    """The bootstrap CLI parses user index input like '1,3' or '1-3'.
    Easy to break, easy to test."""

    def test_parses_comma_list(self):
        from app.evals.bootstrap import _parse_indices

        assert _parse_indices("1,3,5", 10) == [1, 3, 5]

    def test_parses_space_list(self):
        from app.evals.bootstrap import _parse_indices

        assert _parse_indices("1 3 5", 10) == [1, 3, 5]

    def test_parses_range(self):
        from app.evals.bootstrap import _parse_indices

        assert _parse_indices("1-3", 10) == [1, 2, 3]

    def test_parses_mixed(self):
        from app.evals.bootstrap import _parse_indices

        assert _parse_indices("1, 3-5, 7", 10) == [1, 3, 4, 5, 7]

    def test_dedupes(self):
        from app.evals.bootstrap import _parse_indices

        assert _parse_indices("1,1,2-3,3", 10) == [1, 2, 3]

    def test_rejects_out_of_range(self):
        from app.evals.bootstrap import _parse_indices

        with pytest.raises(ValueError, match="out of range"):
            _parse_indices("1,15", 10)

    def test_rejects_garbage(self):
        from app.evals.bootstrap import _parse_indices

        with pytest.raises(ValueError):
            _parse_indices("abc", 10)

    def test_empty_returns_empty(self):
        from app.evals.bootstrap import _parse_indices

        assert _parse_indices("", 10) == []
        assert _parse_indices("   ", 10) == []

    def test_round_trip_jsonl(self):
        from app.evals.bootstrap import _entry_to_jsonl
        from app.evals.goldset import GoldEntry

        e = GoldEntry(
            id="q-001",
            query="Quelle est la fréquence ?",
            language="fr",
            intent="lookup",
            relevant_segment_ids=("vs-a", "vs-b"),
            reference_answer="Chaque jour.",
            notes="",
        )
        line = _entry_to_jsonl(e)
        parsed = json.loads(line)
        assert parsed["id"] == "q-001"
        assert parsed["relevant_segment_ids"] == ["vs-a", "vs-b"]
        # Non-ASCII must round-trip without \u escaping for human readability
        assert "fréquence" in line
