# RAG eval harness

Measures retrieval quality (`recall@k`, `MRR`, `nDCG`) and answer
quality (faithfulness, answer-relevance). Built so every change to
chunking, BM25, fusion, or reranking can be A/B'd on a stable goldset.

## Files

- `goldset.jsonl` — labeled queries. JSON Lines; see `goldset.py` for schema.
- `goldset.py` — strict loader with schema validation.
- `runner.py` — `evaluate_retrieval(goldset, retriever, top_k)` → recall@k / MRR@k / nDCG@k (computed in-house, no deps).
- `judge.py` — `score_faithfulness` / `score_answer_relevance` LLM-as-judge.
- `bootstrap.py` — interactive CLI to label new queries against the running service.

## Bootstrap workflow (first-time setup)

You need labeled queries before any of the eval metrics produce numbers.
The `bootstrap.py` CLI minimizes the friction.

### 1. Reindex with the new chunker

The Phase 1.2 RegulatoryChunker prepends section breadcrumbs to the
text fed to FAISS + BM25. Old vectors don't have breadcrumbs, so for a
true measurement the corpus must be re-embedded.

```bash
# From ai-service-python/
python -m scripts.reset_indexes              # dry-run
python -m scripts.reset_indexes --apply      # actually delete
```

The BM25 pickle is also auto-discarded by `BM25_INDEX_VERSION`
mismatch when the service restarts. FAISS has no equivalent, hence
the manual step.

Then re-ingest. The DB-side `TextSegment` rows are shared with the
.NET service — to fully refresh:

- Easiest: trigger the SharePoint sync (`POST /sync/run` on the .NET
  side) which re-ingests changed documents.
- Per-document: `DELETE /api/documents/{id}` on this service, then
  `POST /api/documents/ingest` with the original file content.

### 2. Run the bootstrap CLI

Start the AI service (`uvicorn app.main:app --reload`) and in another
terminal:

```bash
export AI_SERVICE_API_KEY=...   # same key the service uses
python -m app.evals.bootstrap --top-k 15
```

Per query, the CLI:
1. Asks for the query, language (`fr`/`ar`/`en`), intent
   (`definition`/`procedure`/`list`/`comparison`/`lookup`/`multi_hop`).
2. Hits `POST /api/search?include_answer=false` and prints the top-k
   chunks with their `vector_store_id`.
3. Asks which indices are the gold answers (e.g. `1,3` or `1-3`).
4. Asks for an optional reference answer (used by the LLM-as-judge).
5. Appends one JSONL line to `goldset.jsonl` atomically.

`Ctrl-C` between queries is safe.

### 3. Recommended seed: ≥10 queries per intent class

Aim for 50–100 entries total, balanced across intents and across at
least 5 representative documents. The plan's expected lifts (+15–25%
nDCG@10 for the Phase 1.1 BM25 fix, etc.) are only meaningful at this
scale — a 5-query goldset has too much variance.

## Running the eval

The retrieval eval needs the live FastAPI app's services. From a
script wrapped around the FastAPI lifespan:

```python
from app.evals import load_goldset, evaluate_retrieval
from app.evals.runner import HybridRetrieverProbe

probe = HybridRetrieverProbe(hybrid_retriever, embedding_service)
goldset = load_goldset("app/evals/goldset.jsonl")
metrics = await evaluate_retrieval(goldset, probe, top_k=10)
print(metrics)  # {'recall@5': 0.62, 'recall@10': 0.78, 'mrr@10': 0.45, 'ndcg@10': 0.51, 'n_queries': 50.0}
```

## A/B testing later changes

When Phase 2.1 (reranker), Phase 2.2 (fusion redesign), or Phase 3
(query planning) ships, run the eval twice with the relevant flag on
and off, compare. Promote the change to default only if `nDCG@10` and
`faithfulness` both improve, or one improves while the other doesn't
regress more than 2%.

## Why no metrics library?

`ragas` pulls in `langchain >= 0.3` which conflicts with this project's
pinned `langchain-core==0.3.0` + `langgraph==0.2.0`. The thin
`judge.py` here covers faithfulness and answer-relevance via the
existing `LLMService` and avoids the dep clash. Revisit if/when the
langchain pinning is loosened.

`ranx` (the original retrieval-metrics backend) was removed for the same
class of reason: it pulls the `zlib-state` C extension, which fails to
build in the `python:3.12-slim` runtime image — so the harness could
never run in Docker/CI. recall@k / MRR@k / nDCG@k are a handful of
textbook formulas over the qrels/run dicts; `runner.py` now computes
them in-house (binary relevance), zero dependencies.
