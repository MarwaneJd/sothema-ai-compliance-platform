"""Batch-ingest a folder of local files into the AI service.

Bypasses the .NET DevController (which needs an Entra JWT we don't have
in scripts) by inserting the Document row directly via SQLAlchemy and
then POSTing to the Python AI service's `/api/documents/ingest`.

Reads `AI_SERVICE_API_KEY` and `AI_SERVICE_DATABASE_CONNECTION_STRING`
from the same `.env` the FastAPI app uses.

Usage:
    # Dry-run (default) — list what would be ingested
    python -m scripts.ingest_local_files --dir ./sample_sops

    # Actually ingest
    python -m scripts.ingest_local_files --dir ./sample_sops --apply

    # Single file
    python -m scripts.ingest_local_files --file ./sop-qc-001.pdf --apply

    # Different AI service URL
    python -m scripts.ingest_local_files --dir ./docs --apply \\
        --api-url http://localhost:8000

The script ingests one file at a time so a single failure doesn't
torpedo the batch. Each result is reported on its own line.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"]
)

# Caps so a stray multi-GB file doesn't blow up. Matches the .NET
# DevController's RequestSizeLimit of 50 MB.
MAX_FILE_SIZE = 50 * 1024 * 1024


@dataclass
class IngestResult:
    path: Path
    document_id: uuid.UUID | None
    segments: int
    status: str  # "indexed" | "skipped" | "error"
    error: str = ""


def _scan(target: Path) -> list[Path]:
    """Resolve --dir or --file into a sorted list of allowed-extension files."""
    if target.is_file():
        return [target]
    if not target.is_dir():
        raise FileNotFoundError(f"Path does not exist: {target}")
    return sorted(
        p for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    )


def _validate(path: Path) -> str:
    """Return an error string if the file is not ingestable, else ''."""
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return f"unsupported extension {path.suffix!r}"
    size = path.stat().st_size
    if size == 0:
        return "empty file"
    if size > MAX_FILE_SIZE:
        return f"file too large ({size:,d} bytes > {MAX_FILE_SIZE:,d})"
    return ""


def _guess_content_type(ext: str) -> str:
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "txt": "text/plain",
        "md": "text/markdown",
    }.get(ext, "application/octet-stream")


async def _create_document_row(session: AsyncSession, path: Path) -> uuid.UUID:
    """Insert a Document row, COMMITTING immediately so the AI service
    (which uses a separate SQLAlchemy session) can see it. The .NET
    DevController has the same constraint and handles it the same way.

    On AI failure, callers must explicitly delete the row via
    `_delete_document_row` — flush+rollback won't work because the row
    must already be visible across connections by the time we POST."""
    from app.db.models import Document

    ext = path.suffix.lower().lstrip(".")
    doc = Document(
        Id=uuid.uuid4(),
        SharePointItemId=f"local-{uuid.uuid4()}",
        Title=path.stem,
        SiteId="local-site",
        DriveId="local-drive",
        ContentType=_guess_content_type(ext),
        FileType=ext,
        SharePointUrl=f"file://{path.resolve()}",
        UploadedAt=datetime.utcnow(),
    )
    session.add(doc)
    await session.commit()
    return doc.Id


async def _delete_document_row(session: AsyncSession, document_id: uuid.UUID) -> None:
    """Cleanup helper for when the AI ingest fails after the Document
    row was already committed."""
    from sqlalchemy import delete

    from app.db.models import Document

    await session.execute(delete(Document).where(Document.Id == document_id))
    await session.commit()


async def _post_ingest(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    document_id: uuid.UUID,
    content_b64: str,
    file_type: str,
    title: str,
) -> dict:
    resp = await client.post(
        f"{api_url.rstrip('/')}/api/documents/ingest",
        json={
            "document_id": str(document_id),
            "content": content_b64,
            "file_type": file_type,
            "title": title,
        },
        headers={"X-API-Key": api_key},
        timeout=300.0,  # large PDFs can take minutes to embed on CPU
    )
    resp.raise_for_status()
    return resp.json()


async def _ingest_one(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    session_factory,
    path: Path,
) -> IngestResult:
    """Insert + commit the Document row, then POST the file. On AI
    failure, explicitly delete the orphaned row — it had to be committed
    before the POST because the AI service uses a separate connection
    and SQL Server's default isolation hides uncommitted writes."""
    err = _validate(path)
    if err:
        return IngestResult(path=path, document_id=None, segments=0, status="skipped", error=err)

    content = path.read_bytes()
    content_b64 = base64.b64encode(content).decode("ascii")
    ext = path.suffix.lower().lstrip(".")

    # Step 1: commit the Document row in its own session.
    async with session_factory() as insert_session:
        try:
            doc_id = await _create_document_row(insert_session, path)
        except Exception as e:
            await insert_session.rollback()
            return IngestResult(
                path=path, document_id=None, segments=0,
                status="error", error=f"DB insert failed: {e}",
            )

    # Step 2: POST to the AI service. On failure, clean up the orphan.
    try:
        response = await _post_ingest(
            client, api_url, api_key, doc_id, content_b64, ext, path.stem
        )
    except Exception as e:
        async with session_factory() as cleanup_session:
            try:
                await _delete_document_row(cleanup_session, doc_id)
            except Exception:
                pass  # don't mask the original AI error with a cleanup error
        return IngestResult(
            path=path, document_id=doc_id, segments=0,
            status="error", error=f"AI ingest failed: {e}",
        )

    return IngestResult(
        path=path,
        document_id=doc_id,
        segments=response.get("segments_created", 0),
        status="indexed",
    )


def _print_plan(files: list[Path]) -> None:
    if not files:
        print("No ingestable files found.")
        return
    total = sum(p.stat().st_size for p in files)
    print(f"Found {len(files)} file(s), total {total:,d} bytes:\n")
    for p in files:
        size = p.stat().st_size
        err = _validate(p)
        marker = "  " if not err else "✗ "
        suffix = "" if not err else f"  ({err})"
        print(f"  {marker}{p.name:<40s} {size:>12,d} bytes{suffix}")


async def main_async(args: argparse.Namespace) -> int:
    target = args.file or args.dir
    if target is None:
        print("error: --dir or --file is required", file=sys.stderr)
        return 2

    try:
        files = _scan(target)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    _print_plan(files)
    if not files:
        return 0

    if not args.apply:
        print("\nDRY RUN — re-run with --apply to actually ingest.")
        return 0

    api_key = args.api_key or settings.api_key
    if not api_key:
        print("error: --api-key not provided and AI_SERVICE_API_KEY not set", file=sys.stderr)
        return 2

    # Defer DB import until --apply so dry-run works without a live DB.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.database_connection_string, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    print(f"\nIngesting {len(files)} file(s) → {args.api_url} ...\n")

    async with httpx.AsyncClient() as client:
        successes = 0
        for path in files:
            result = await _ingest_one(client, args.api_url, api_key, session_factory, path)
            if result.status == "indexed":
                successes += 1
                print(f"  ✓ {path.name:<40s} {result.segments:>4d} chunks  doc_id={result.document_id}")
            elif result.status == "skipped":
                print(f"  ⊘ {path.name:<40s} skipped: {result.error}")
            else:
                print(f"  ✗ {path.name:<40s} ERROR: {result.error}")

    await engine.dispose()
    print(f"\n{successes}/{len(files)} ingested successfully.")
    return 0 if successes == len(files) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", type=Path, help="Directory of files to ingest")
    src.add_argument("--file", type=Path, help="Single file to ingest")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None, help="Defaults to AI_SERVICE_API_KEY env var.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the ingest. Without this, only print the plan.",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
