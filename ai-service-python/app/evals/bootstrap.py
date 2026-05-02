"""Interactive goldset bootstrap CLI.

Walks the user through labeling a query end-to-end:

  1. Prompt for the query, intent, language.
  2. Hit /api/search?include_answer=false on the running AI service to
     fetch the top-k retrieved chunks.
  3. Display each chunk with its VectorStoreId and let the user mark
     which are "gold" (relevant).
  4. Optionally prompt for a reference answer.
  5. Append a valid GoldEntry JSON line to goldset.jsonl.

Usage (with the AI service running on localhost:8000):

    python -m app.evals.bootstrap \\
        --api-url http://localhost:8000 \\
        --api-key $AI_SERVICE_API_KEY \\
        --top-k 15

Each query is appended atomically — Ctrl-C between queries is safe.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx

from app.evals.goldset import ALLOWED_INTENTS, ALLOWED_LANGUAGES, GoldEntry, load_goldset

DEFAULT_GOLDSET = Path(__file__).parent / "goldset.jsonl"


def _prompt(label: str, default: str = "", choices: list[str] | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    if choices:
        suffix += f" ({'/'.join(choices)})"
    while True:
        raw = input(f"{label}{suffix}: ").strip()
        value = raw or default
        if not value:
            print("  → required, try again")
            continue
        if choices and value not in choices:
            print(f"  → must be one of: {', '.join(choices)}")
            continue
        return value


def _fetch_search(api_url: str, api_key: str, query: str, top_k: int) -> list[dict]:
    """Hit POST /api/search with include_answer=false. Returns the raw `results` list."""
    resp = httpx.post(
        f"{api_url.rstrip('/')}/api/search",
        json={"query": query, "top_k": top_k, "include_answer": False},
        headers={"X-API-Key": api_key},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def _print_results(results: list[dict]) -> None:
    if not results:
        print("\n(No results returned. Index may be empty — re-ingest first.)\n")
        return
    print(f"\n{len(results)} candidates returned:\n")
    for i, r in enumerate(results, start=1):
        vsid = r.get("vector_store_id") or "(missing — service version too old)"
        title = r.get("document_title", "?")
        chunk_idx = r.get("chunk_index", "?")
        score = r.get("relevance_score", 0.0)
        preview = (r.get("segment_content") or "").strip().replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:200] + "…"
        print(f"  [{i:>2}]  vs={vsid}  doc={title!r}  chunk={chunk_idx}  rrf={score:.4f}")
        print(f"        {preview}\n")


def _parse_indices(raw: str, n: int) -> list[int]:
    """Parse '1,3,5' or '1 3 5' or '1-3' into 1-indexed positions, validated."""
    if not raw.strip():
        return []
    out: set[int] = set()
    for tok in raw.replace(",", " ").split():
        if "-" in tok:
            try:
                lo, hi = (int(x) for x in tok.split("-", 1))
            except ValueError as e:
                raise ValueError(f"bad range {tok!r}") from e
            for i in range(lo, hi + 1):
                if i < 1 or i > n:
                    raise ValueError(f"index {i} out of range 1..{n}")
                out.add(i)
        else:
            try:
                i = int(tok)
            except ValueError as e:
                raise ValueError(f"bad index {tok!r}") from e
            if i < 1 or i > n:
                raise ValueError(f"index {i} out of range 1..{n}")
            out.add(i)
    return sorted(out)


def _label_one(api_url: str, api_key: str, top_k: int, existing_ids: set[str]) -> GoldEntry | None:
    print("\n" + "=" * 70)
    print("New goldset query")
    print("=" * 70)

    query = _prompt("Query (FR/AR/EN)")
    language = _prompt("Language", default="fr", choices=sorted(ALLOWED_LANGUAGES))
    intent = _prompt("Intent", default="lookup", choices=sorted(ALLOWED_INTENTS))

    try:
        results = _fetch_search(api_url, api_key, query, top_k)
    except httpx.HTTPError as e:
        print(f"\n  ✗ Search request failed: {e}")
        return None

    _print_results(results)
    if not results:
        return None

    while True:
        raw = input("Mark relevant chunks by index (e.g. '1,3' or '1-3'), or 'skip' to abandon: ").strip()
        if raw.lower() in ("skip", "s", "q", "quit"):
            return None
        try:
            picks = _parse_indices(raw, len(results))
        except ValueError as e:
            print(f"  → {e}")
            continue
        if not picks:
            print("  → at least one index required (or 'skip')")
            continue
        relevant_ids = [results[i - 1].get("vector_store_id") for i in picks]
        relevant_ids = [vid for vid in relevant_ids if vid]
        if not relevant_ids:
            print("  → selected results have no vector_store_id; cannot label. Skipping.")
            return None
        break

    reference = input("Reference answer (optional, Enter to skip): ").strip()
    notes = input("Notes (optional, Enter to skip): ").strip()

    # Generate a stable-ish id; allow override
    suggested_id = f"q-{uuid.uuid4().hex[:8]}"
    while True:
        entry_id = input(f"Entry id [{suggested_id}]: ").strip() or suggested_id
        if entry_id in existing_ids:
            print(f"  → id {entry_id!r} already exists in goldset. Pick another.")
            continue
        break

    return GoldEntry(
        id=entry_id,
        query=query,
        language=language,  # type: ignore[arg-type]
        intent=intent,  # type: ignore[arg-type]
        relevant_segment_ids=tuple(relevant_ids),
        reference_answer=reference,
        notes=notes,
    )


def _entry_to_jsonl(e: GoldEntry) -> str:
    return json.dumps(
        {
            "id": e.id,
            "query": e.query,
            "language": e.language,
            "intent": e.intent,
            "relevant_segment_ids": list(e.relevant_segment_ids),
            "reference_answer": e.reference_answer,
            "notes": e.notes,
        },
        ensure_ascii=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Defaults to AI_SERVICE_API_KEY env var.",
    )
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument(
        "--goldset",
        type=Path,
        default=DEFAULT_GOLDSET,
        help=f"Path to goldset JSONL (default: {DEFAULT_GOLDSET})",
    )
    args = parser.parse_args()

    if args.api_key is None:
        import os
        args.api_key = os.environ.get("AI_SERVICE_API_KEY")
    if not args.api_key:
        print("error: --api-key not provided and AI_SERVICE_API_KEY not set", file=sys.stderr)
        return 2

    existing = load_goldset(args.goldset)
    existing_ids = {e.id for e in existing}
    print(f"Loaded {len(existing)} existing entries from {args.goldset}")
    print(f"Querying {args.api_url} with top_k={args.top_k}\n")
    print("Ctrl-C between queries to stop. Each entry is appended atomically.")

    appended = 0
    try:
        while True:
            entry = _label_one(args.api_url, args.api_key, args.top_k, existing_ids)
            if entry is None:
                print("(skipped)")
                continue
            line = _entry_to_jsonl(entry)
            with args.goldset.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            existing_ids.add(entry.id)
            appended += 1
            print(f"\n  ✓ Appended entry {entry.id!r}. Total in file: {len(existing) + appended}")
    except (KeyboardInterrupt, EOFError):
        print(f"\n\nStopped. Appended {appended} new entries this session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
