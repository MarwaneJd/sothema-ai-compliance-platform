"""Resolve `PENDING` relevant_segment_ids in the disposable starter goldset.

For each goldset entry whose relevant_segment_ids is ["PENDING"], this:
  1. Calls POST /api/search (include_answer=false) with the query.
  2. Scores every returned candidate by LEXICAL OVERLAP between the candidate
     chunk content and the entry's `reference_answer` — NOT by the retriever's
     own rank. This is deliberate: picking the retriever's rank-1 chunk as
     "gold" would make recall@k trivially ~1.0 and the eval meaningless. The
     reference answers were authored from the source PDFs independently of the
     retriever, so overlap-based selection breaks that circularity.
  3. Picks the best chunk(s); if nothing clears the overlap threshold the
     entry is marked ["NEEDS_HUMAN"] rather than force-labeled (pooling bias:
     the true chunk may simply not have been retrieved).
  4. Rewrites goldset.jsonl in place — comment lines preserved verbatim — and
     appends a resolution trace to each `notes` (chosen rank + overlap score)
     so the retrieval reality is visible even before the formal eval runs.

Usage (AI service must be running):
    python -m scripts.resolve_goldset_ids --api-url http://localhost:8000 \
        --api-key $AI_SERVICE_API_KEY --top-k 15
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

import httpx

DEFAULT_GOLDSET = Path(__file__).parent.parent / "app" / "evals" / "goldset.jsonl"

# Min content-words from the reference answer that must appear in a candidate
# chunk for it to count as gold. Looser for list/comparison/multi_hop because
# their answers span more text than any single chunk holds.
ACCEPT_THRESHOLD = {
    "lookup": 0.45,
    "definition": 0.45,
    "procedure": 0.40,
    "list": 0.32,
    "comparison": 0.25,
    "multi_hop": 0.25,
}
MULTI_CHUNK_INTENTS = {"comparison", "multi_hop"}


def _norm(text: str) -> set[str]:
    """Lowercase, strip accents, keep content words (len >= 4). Crude for AR
    (no stemming) — AR entries will usually fall to NEEDS_HUMAN, which is the
    honest outcome for a disposable set."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    )
    toks = "".join(c if c.isalnum() else " " for c in stripped).split()
    return {t for t in toks if len(t) >= 4}


def _overlap(reference: str, candidate_content: str) -> float:
    """Fraction of reference-answer content words present in the candidate."""
    ref = _norm(reference)
    if not ref:
        return 0.0
    cand = _norm(candidate_content)
    return len(ref & cand) / len(ref)


def _search(client: httpx.Client, api_url: str, api_key: str, query: str, top_k: int) -> list[dict]:
    r = client.post(
        f"{api_url.rstrip('/')}/api/search",
        json={"query": query, "top_k": top_k, "include_answer": False},
        headers={"X-API-Key": api_key},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def _resolve_entry(entry: dict, results: list[dict]) -> tuple[list[str], str]:
    """Return (relevant_segment_ids, resolution_note)."""
    ref = entry.get("reference_answer", "")
    if not ref or not results:
        return ["NEEDS_HUMAN"], "no_reference_or_no_results"

    scored = []
    for rank, r in enumerate(results, start=1):
        vsid = r.get("vector_store_id")
        if not vsid:
            continue
        scored.append((_overlap(ref, r.get("segment_content", "")), rank, vsid))
    if not scored:
        return ["NEEDS_HUMAN"], "candidates_missing_vector_store_id"

    scored.sort(key=lambda x: x[0], reverse=True)
    threshold = ACCEPT_THRESHOLD.get(entry["intent"], 0.40)
    best_ov, best_rank, best_id = scored[0]
    if best_ov < threshold:
        return (
            ["NEEDS_HUMAN"],
            f"best_overlap={best_ov:.2f}<thr={threshold:.2f} (rank{best_rank})",
        )

    if entry["intent"] in MULTI_CHUNK_INTENTS:
        # Take up to 2 chunks above a relaxed bar (multi-source answers).
        picked = [(s, rk, vid) for s, rk, vid in scored if s >= threshold][:2]
        ids = [vid for _, _, vid in picked]
        trace = ", ".join(f"rank{rk}/ov{ s:.2f}" for s, rk, _ in picked)
        return ids, f"multi:{trace}"

    return [best_id], f"rank{best_rank}/ov{best_ov:.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api-url", default="http://localhost:8000")
    ap.add_argument("--api-key", default=os.environ.get("AI_SERVICE_API_KEY"))
    ap.add_argument("--top-k", type=int, default=15)
    ap.add_argument("--goldset", type=Path, default=DEFAULT_GOLDSET)
    ap.add_argument("--dry-run", action="store_true", help="Print, do not rewrite the file.")
    args = ap.parse_args()

    if not args.api_key:
        print("error: --api-key or AI_SERVICE_API_KEY required", file=sys.stderr)
        return 2

    raw_lines = args.goldset.read_text(encoding="utf-8").splitlines()
    out_lines: list[str] = []
    resolved = needs_human = skipped = 0
    rank_hist: dict[str, int] = {}

    with httpx.Client() as client:
        for line in raw_lines:
            s = line.strip()
            if not s or s.startswith("#"):
                out_lines.append(line)
                continue
            entry = json.loads(s)
            if entry.get("relevant_segment_ids") != ["PENDING"]:
                out_lines.append(line)
                skipped += 1
                continue

            try:
                results = _search(client, args.api_url, args.api_key, entry["query"], args.top_k)
            except httpx.HTTPError as e:
                print(f"  ✗ {entry['id']}: search failed ({e}) — left PENDING")
                out_lines.append(line)
                continue

            ids, note = _resolve_entry(entry, results)
            entry["relevant_segment_ids"] = ids
            entry["notes"] = f"{entry.get('notes','')} | resolved: {note}".strip(" |")
            out_lines.append(json.dumps(entry, ensure_ascii=False))

            if ids == ["NEEDS_HUMAN"]:
                needs_human += 1
                tag = "needs_human"
            else:
                resolved += 1
                tag = "OK"
                first_rank = note.split("rank")[1].split("/")[0].split(",")[0]
                rank_hist[first_rank] = rank_hist.get(first_rank, 0) + 1
            print(f"  [{tag:^11}] {entry['id']:<10} {note}")

    if not args.dry_run:
        args.goldset.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print("\n" + "=" * 56)
    print(f"resolved={resolved}  needs_human={needs_human}  skipped(non-PENDING)={skipped}")
    if rank_hist:
        order = sorted(rank_hist, key=lambda r: int(r))
        print("gold-chunk retrieval rank (recall reality):")
        for r in order:
            print(f"  rank {r:>2}: {'#' * rank_hist[r]} ({rank_hist[r]})")
    if args.dry_run:
        print("(dry-run — file NOT modified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
