"""Tests for scripts/ingest_local_files.py.

Pure helpers (_scan, _validate, _guess_content_type, _print_plan) are
exercised directly. The HTTP path uses httpx.MockTransport (built-in,
no respx version drift). The end-to-end ingest is verified via mocked
session_factory + MockTransport — checks the rollback contract without
touching SQL Server.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from scripts.ingest_local_files import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    _guess_content_type,
    _ingest_one,
    _post_ingest,
    _print_plan,
    _scan,
    _validate,
)

API_URL = "http://test-ai:8000"
API_KEY = "test-key"


def _write(tmp: Path, name: str, content: bytes = b"hello world\n") -> Path:
    p = tmp / name
    p.write_bytes(content)
    return p


def _mock_client(handler) -> httpx.AsyncClient:
    """httpx client whose transport is a `MockTransport(handler)`.

    `handler(request) -> httpx.Response`. Lets us inspect the captured
    request without depending on respx.
    """
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _fake_session_factory(execute_side_effect=None, flush_side_effect=None):
    """Returns a callable that produces an async-context-manager session
    with mocked add/flush/commit/rollback. Use to verify the script's
    DB transaction lifecycle without a real engine.

    Each call returns a NEW session so we can verify the script uses
    separate sessions for insert vs cleanup (ingest_one now opens two)."""
    sessions: list[MagicMock] = []

    @asynccontextmanager
    async def factory():
        s = MagicMock()
        s.add = MagicMock()
        s.flush = AsyncMock(side_effect=flush_side_effect)
        s.execute = AsyncMock(side_effect=execute_side_effect)
        s.commit = AsyncMock()
        s.rollback = AsyncMock()
        sessions.append(s)
        yield s

    factory.sessions = sessions  # list of all sessions opened during the test
    return factory


# --- Pure helpers --------------------------------------------------------


class TestScan:
    def test_single_file(self, tmp_path: Path):
        p = _write(tmp_path, "x.txt")
        assert _scan(p) == [p]

    def test_directory_filters_by_extension(self, tmp_path: Path):
        good = _write(tmp_path, "a.txt")
        also_good = _write(tmp_path, "b.pdf", content=b"%PDF-1.4\n")
        _write(tmp_path, "junk.zip")
        result = _scan(tmp_path)
        assert good in result
        assert also_good in result
        assert all(p.suffix.lower() in ALLOWED_EXTENSIONS for p in result)

    def test_directory_sorted(self, tmp_path: Path):
        _write(tmp_path, "c.txt")
        _write(tmp_path, "a.txt")
        _write(tmp_path, "b.txt")
        names = [p.name for p in _scan(tmp_path)]
        assert names == sorted(names)

    def test_missing_path_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            _scan(tmp_path / "nope")


class TestValidate:
    def test_unsupported_extension(self, tmp_path: Path):
        p = _write(tmp_path, "a.zip")
        assert "unsupported" in _validate(p)

    def test_empty_file(self, tmp_path: Path):
        p = _write(tmp_path, "a.txt", content=b"")
        assert _validate(p) == "empty file"

    def test_too_large(self, tmp_path: Path, monkeypatch):
        p = _write(tmp_path, "big.txt", content=b"x" * 100)
        import scripts.ingest_local_files as mod
        monkeypatch.setattr(mod, "MAX_FILE_SIZE", 50)
        assert "too large" in _validate(p)

    def test_ok(self, tmp_path: Path):
        assert _validate(_write(tmp_path, "a.txt")) == ""


class TestGuessContentType:
    def test_known(self):
        assert _guess_content_type("pdf") == "application/pdf"
        assert _guess_content_type("docx").endswith("wordprocessingml.document")
        assert _guess_content_type("txt") == "text/plain"

    def test_unknown_falls_back(self):
        assert _guess_content_type("zip") == "application/octet-stream"


class TestPrintPlan:
    def test_empty(self, capsys):
        _print_plan([])
        assert "No ingestable" in capsys.readouterr().out

    def test_marks_invalid(self, tmp_path: Path, capsys):
        p = _write(tmp_path, "a.txt", content=b"")
        _print_plan([p])
        out = capsys.readouterr().out
        assert "✗" in out
        assert "empty file" in out


# --- HTTP path -----------------------------------------------------------


class TestPostIngest:
    @pytest.mark.asyncio
    async def test_includes_api_key_header_and_payload(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"segments_created": 5})

        doc_id = uuid.uuid4()
        async with _mock_client(handler) as client:
            result = await _post_ingest(
                client, API_URL, API_KEY, doc_id, "QkFTRTY0", "pdf", "test-title"
            )

        assert captured["method"] == "POST"
        assert captured["url"] == f"{API_URL}/api/documents/ingest"
        assert captured["headers"]["x-api-key"] == API_KEY
        assert captured["body"] == {
            "document_id": str(doc_id),
            "content": "QkFTRTY0",
            "file_type": "pdf",
            "title": "test-title",
        }
        assert result["segments_created"] == 5

    @pytest.mark.asyncio
    async def test_raises_on_4xx(self):
        def handler(_request):
            return httpx.Response(401, json={"detail": "bad key"})

        async with _mock_client(handler) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await _post_ingest(
                    client, API_URL, "wrong", uuid.uuid4(), "x", "txt", "title"
                )


# --- End-to-end (mocked DB session + mocked HTTP) ------------------------


class TestIngestOne:
    @pytest.mark.asyncio
    async def test_happy_path(self, tmp_path: Path, monkeypatch):
        async def _fake_create(session, path):
            await session.commit()  # mimic the real fn, which commits
            return uuid.UUID("11111111-1111-1111-1111-111111111111")

        delete_called = MagicMock()

        async def _fake_delete(session, doc_id):
            delete_called(doc_id)

        import scripts.ingest_local_files as mod
        monkeypatch.setattr(mod, "_create_document_row", _fake_create)
        monkeypatch.setattr(mod, "_delete_document_row", _fake_delete)

        def handler(_request):
            return httpx.Response(200, json={"segments_created": 7})

        factory = _fake_session_factory()
        p = _write(tmp_path, "test.txt")

        async with _mock_client(handler) as client:
            result = await _ingest_one(client, API_URL, API_KEY, factory, p)

        assert result.status == "indexed"
        assert result.segments == 7
        assert str(result.document_id) == "11111111-1111-1111-1111-111111111111"
        # Only one session opened (the insert); cleanup not needed
        assert len(factory.sessions) == 1
        delete_called.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_orphan_on_ai_failure(self, tmp_path: Path, monkeypatch):
        async def _fake_create(session, path):
            await session.commit()
            return uuid.UUID("22222222-2222-2222-2222-222222222222")

        delete_called = MagicMock()

        async def _fake_delete(session, doc_id):
            delete_called(doc_id)

        import scripts.ingest_local_files as mod
        monkeypatch.setattr(mod, "_create_document_row", _fake_create)
        monkeypatch.setattr(mod, "_delete_document_row", _fake_delete)

        def handler(_request):
            return httpx.Response(500, json={"detail": "boom"})

        factory = _fake_session_factory()
        p = _write(tmp_path, "test.txt")

        async with _mock_client(handler) as client:
            result = await _ingest_one(client, API_URL, API_KEY, factory, p)

        assert result.status == "error"
        assert "AI ingest failed" in result.error
        # CRITICAL: cleanup must have run to remove the orphan Document row.
        delete_called.assert_called_once_with(uuid.UUID("22222222-2222-2222-2222-222222222222"))
        # Two sessions: one insert, one cleanup
        assert len(factory.sessions) == 2

    @pytest.mark.asyncio
    async def test_rolls_back_on_db_insert_failure(self, tmp_path: Path, monkeypatch):
        async def _fake_create(session, path):
            raise RuntimeError("table doesn't exist")

        async def _fake_delete(session, doc_id):
            raise AssertionError("delete must not run when insert never happened")

        import scripts.ingest_local_files as mod
        monkeypatch.setattr(mod, "_create_document_row", _fake_create)
        monkeypatch.setattr(mod, "_delete_document_row", _fake_delete)

        ai_called = MagicMock()

        def handler(_request):
            ai_called()
            return httpx.Response(200, json={"segments_created": 1})

        factory = _fake_session_factory()
        p = _write(tmp_path, "test.txt")

        async with _mock_client(handler) as client:
            result = await _ingest_one(client, API_URL, API_KEY, factory, p)

        assert result.status == "error"
        assert "DB insert failed" in result.error
        assert result.document_id is None
        # Insert session opened and rollback called; cleanup session not opened
        assert len(factory.sessions) == 1
        factory.sessions[0].rollback.assert_awaited_once()
        ai_called.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_invalid_file_without_touching_db_or_http(self, tmp_path: Path):
        ai_called = MagicMock()

        def handler(_request):
            ai_called()
            return httpx.Response(200)

        factory = _fake_session_factory()
        p = _write(tmp_path, "empty.txt", content=b"")

        async with _mock_client(handler) as client:
            result = await _ingest_one(client, API_URL, API_KEY, factory, p)

        assert result.status == "skipped"
        assert "empty" in result.error
        assert result.document_id is None
        # Neither DB nor HTTP touched
        ai_called.assert_not_called()
        assert factory.sessions == []


class TestConstants:
    def test_max_file_size_matches_dotnet(self):
        # .NET DevController has [RequestSizeLimit(50 * 1024 * 1024)] — keep aligned.
        assert MAX_FILE_SIZE == 50 * 1024 * 1024
