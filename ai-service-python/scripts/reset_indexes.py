"""Wipe the on-disk FAISS + BM25 indexes so they rebuild from scratch.

Use after a chunking or embedding change has invalidated the existing
vectors — for example, after the Phase 1.2 RegulatoryChunker switched
the indexed text to include section breadcrumbs. The BM25 pickle is
also auto-discarded by version mismatch when its `BM25_INDEX_VERSION`
changes, but FAISS has no equivalent guardrail and needs a manual wipe.

Usage:
    python -m scripts.reset_indexes              # dry-run, just print
    python -m scripts.reset_indexes --apply      # actually delete

The DB-side `TextSegment` rows are NOT touched — they're shared with the
.NET service. To get a true full re-embed with breadcrumbs you must
delete the segments via the .NET side (or call DELETE /api/documents/{id}
on this service for each document) and then re-ingest.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the index files. Without this flag, only prints what would be deleted.",
    )
    args = parser.parse_args()

    base = Path(settings.faiss_index_path)
    targets = [
        base / "faiss.index",
        base / "faiss_meta.pkl",
        base / "bm25_index.pkl",
    ]

    found = [p for p in targets if p.exists()]
    if not found:
        print(f"No index files found under {base.resolve()}")
        return 0

    print(f"Index files under {base.resolve()}:")
    total = 0
    for p in found:
        size = p.stat().st_size
        total += size
        print(f"  {p.name:24s} {size:>12,d} bytes")
    print(f"  Total: {total:,d} bytes\n")

    if not args.apply:
        print("DRY RUN — re-run with --apply to actually delete.")
        print("After deletion, restart the AI service and re-ingest documents")
        print("(via the .NET backend's SharePoint sync, or by calling")
        print("POST /api/documents/ingest for each document).")
        return 0

    for p in found:
        p.unlink()
        print(f"Deleted {p}")
    print("\nDone. Restart the AI service to reinitialize empty indexes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
