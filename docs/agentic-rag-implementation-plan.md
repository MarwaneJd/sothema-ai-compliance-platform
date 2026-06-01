# Agentic RAG Upgrade — Sothema Compliance Platform

## Status (2026-05-14)

| Phase | State | Notes |
|---|---|---|
| Phase 1 — Cross-encoder reranker | ✅ Shipped | Model swapped during implementation (see Phase 1 §Implementation reality) |
| Phase 2 — Multi-query rewriting + LLM tier abstraction | ✅ Shipped | `MultiQueryRetriever` wired into `/api/search`; expansion audit-logging deferred |
| Phase 3 — LangGraph agentic loop | ✅ Shipped | `/api/agentic-search` live; .NET pass-through + frontend "Deep Analysis" mode shipped |
| Phase 3 hardening (synthesis + rate-limit resilience) | ✅ Shipped 2026-05-14 | See §"Phase 3 hardening" below |
| Conversation memory (Phase 4) | ⏳ Deferred | |
| Streaming (Phase 5) | ⏳ Deferred | |

**Production hardening done alongside Phase 1+2:**
- System prompt tightened with strict no-training-knowledge rule + `[Source N]` citation format ([pipeline.py:15-39](../ai-service-python/app/rag/pipeline.py#L15-L39)).
- Two PDFs found silently un-indexed (`partie_i-chapitre_4frdef.pdf`, `european-regulatory-system-medicines_fr.pdf`) — re-ingested. Root cause (silent ingest failures in [DevController.cs:92-95](../backend-dotnet-api/src/Sothema.Compliance.Api/Controllers/DevController.cs#L92-L95)) tracked under Open Items.

**Measured latencies (Docker-for-Mac, native arm64, Groq Llama-3.3-70B paid tier, 2026-05-14):**
- **Fast mode** (`/api/search`): ~5.4s p50 end-to-end. On prod-class CPU/GPU should be well under the 3s SLA.
- **Deep Analysis** (`/api/agentic-search`):
  - **single_pass simple queries** (plan + generate + verify, reflect bypassed): **~6–9s** end-to-end.
  - **multi_pass comparative/multi-hop queries** (plan + retrieve over N sub-queries + synthesis generate + verify, no refine loop): **~9–11s** end-to-end. Hard wall-clock cap now 25s (was 15s — Groq's per-call retries can eat 5-10s under load).

## Context

The current `/api/search` endpoint is a single-pass hybrid RAG: embed query → FAISS + BM25 → RRF fuse → optional LLM answer. It works, but it has no reranking, no query rewriting, no iterative refinement, and no groundedness checks. Complex compliance questions ("Is our batch release procedure aligned with EU GMP Annex 16 §1.7?") often need multiple retrieval steps and source verification — single-pass RAG underperforms on those.

This plan upgrades the AI service to **agentic RAG**: a LangGraph ReAct-style state machine that wraps existing primitives as tools, with a planner, iterative retriever, reflection step, and groundedness verifier. The existing `/api/search` and `/api/analyze` endpoints stay untouched (zero regression). LangGraph and LangChain are already in [requirements.txt](../ai-service-python/requirements.txt) — no new heavy deps.

**Scope decisions (confirmed with user):**
- Ship **Phases 1–3** this round (reranking → multi-query rewriting → agent loop). Conversation memory and streaming deferred.
- **No permission filtering** — all authenticated users see all docs today, so the agent retrieves from the full corpus. (If that changes, revisit Phase 3 to thread `allowed_doc_ids` through tool calls.)
- **Latency budget: p95 5–15s** for Deep Search; **p95 <3s** for Fast mode. Agent has hard wall-clock cap of 15s, max 2 retrieval iterations, max 6 LLM calls per query. Dev numbers (on Groq) will be ~3–5× faster than prod (Azure) — they prove the pipeline works, not that it meets SLA.
- **LLM providers — dev vs. prod split:**
  - **Production (Azure-only):** Azure OpenAI **GPT-5.4** for reasoning steps (`plan`, `generate`); Azure OpenAI **GPT-5.4 mini** for cheap steps (query expansion, `reflect`, `refine_query`, `verify`, eval judge). Pharmaceutical compliance + data residency = Azure-only in prod.
  - **Development (Groq-only, no Azure credentials yet):** **Groq `llama-3.3-70b-versatile`** for both tiers. Free, fast, and lets us iterate on the pipeline before Azure credentials land.
  - Code routes calls through a **tier abstraction** (`tier="reasoning"` vs. `tier="fast"`); tiers map to provider+model via env vars. Provider swap = config change, no code change.
- **Two user-facing modes:**
  - **Fast** — hybrid (FAISS + BM25 + RRF) + cross-encoder reranker (Phase 1) + multi-query rewriting (Phase 2) + single-pass LLM answer. Backed by `/api/search`. p95 <3s.
  - **Deep Search** — full agentic loop (Phase 3, also using reranker and multi-query expansion internally). Backed by `/api/agentic-search`. p95 5–15s.
  - The existing "Sources Only" view becomes a dev/admin-only toggle (gated by an env flag or admin role) — preserved for goldset labeling and retrieval debugging, hidden from end users.

## Phase 1 — Cross-Encoder Reranking ✅ Shipped (2026-05-10)

Largest recall/nDCG win per line of code. No agentic complexity, no extra LLM calls. Drop-in.

**Model — implementation reality:** spec'd as `BAAI/bge-reranker-v2-m3` (multilingual FR/AR/EN, strongest quality) but on Docker-for-Mac CPU it took **~60s per query** for 40 candidates — unusable. Swapped to **`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`** (also FR/AR/EN, mMARCO-trained MiniLM): **~3s for the same 40 candidates** on the same hardware. Quality is ~80–90% of bge-v2-m3 by published benchmarks; the precision recovered by reranking 40 candidates vs. 10 vastly outweighs the per-pair quality drop. **Swap back to bge-v2-m3 if production runs on GPU or beefy server CPU.**

A `reranker_max_length: int = 256` token cap was added so future model swaps don't blow up on long pharma chunks (chunks average ~580 tokens — without the cap the cross-encoder processes the full sequence, scaling badly on CPU).

**Files added:**
- [ai-service-python/app/rag/reranker.py](../ai-service-python/app/rag/reranker.py) — `CrossEncoderReranker.rerank(query, candidates, candidate_texts, top_n)`. `predict()` runs in a thread pool (`asyncio.to_thread`) so the event loop isn't blocked.

**Files modified:**
- [ai-service-python/app/rag/pipeline.py](../ai-service-python/app/rag/pipeline.py) — new `_retrieve_and_rerank()` helper. Fetches `top_k * fetch_multiplier` candidates, loads their text from the segment repo, reranks to `top_k`. Both `query()` and `retrieve_only()` go through this helper.
- [ai-service-python/app/dependencies.py](../ai-service-python/app/dependencies.py) — `get_reranker()` reads `app.state.reranker` (loaded once at startup, not lazy on first request).
- [ai-service-python/app/main.py](../ai-service-python/app/main.py) — lifespan loads the reranker into `app.state.reranker` after FAISS/BM25.
- [ai-service-python/app/config.py](../ai-service-python/app/config.py) — `enable_reranker: bool = True`, `reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"`, `reranker_fetch_multiplier: int = 4`, `reranker_max_length: int = 256`.
- [ai-service-python/Dockerfile](../ai-service-python/Dockerfile) — pre-bakes the reranker model alongside the embedding model so cold start doesn't wait on HuggingFace.

**Verification:** [`RerankedRetrieverProbe`](../ai-service-python/app/evals/runner.py) added. Acceptance gates (recall@10 +5%) **not yet run** — pending goldset sizing (Open Items).

## Phase 2 — Multi-Query Rewriting + LLM Tier Abstraction ✅ Shipped (2026-05-10)

Cheap one-shot expansion before retrieval. Better than HyDE for regulatory text (HyDE fabricates terminology and poisons retrieval). **Ships into both modes:** powers Fast mode directly (called inside `/api/search`) and will power Deep Search (called inside the agent's `plan` node via the `expand_query` tool when Phase 3 lands).

**Why in Fast mode too (precision-critical platform):** the reranker improves *ordering* of candidates but cannot promote a chunk that never made it into the candidate pool. Multi-query rewriting raises *recall* by catching phrasing variance ("exigences libération lots" → "qualification certification BPF"). On a compliance product, a missed clause is worse than a slightly slower response.

**Files added:**
- [ai-service-python/app/rag/query_expander.py](../ai-service-python/app/rag/query_expander.py) — `QueryExpander.expand(query, n=3) -> list[str]`. One LLM call (`tier="fast"`) returning a Pydantic `ExpandedQueries(queries: list[str])`. Detects dominant script (Arabic Unicode block) to pick prompt language; default French/English mixed prompt. **LRU cache, 2048 entries**. **800ms timeout with fallback to original-query-only** — degrades gracefully rather than blocks the Fast SLA.
- [ai-service-python/app/rag/multi_query.py](../ai-service-python/app/rag/multi_query.py) — orchestrates retrieval across the original + N rewritten queries, fuses results with RRF. Original-query retrieval runs **in parallel** with the LLM expansion call. `last_expanded_queries` exposed on the retriever for audit hookup.

**Files modified:**
- [ai-service-python/app/services/llm.py](../ai-service-python/app/services/llm.py) — refactored to **tier abstraction**: `generate(messages, *, tier="reasoning"|"fast", ...)` and `generate_structured(...)`. Two providers (Azure prod, Groq dev); tier→model resolution from env. Backwards-compat: `LLMService.model` property still returns the reasoning-tier model.
- [ai-service-python/app/rag/hybrid_retriever.py](../ai-service-python/app/rag/hybrid_retriever.py) — RRF block extracted into module-level `reciprocal_rank_fusion(rankings, k=60, top_k=None)` reused by `HybridRetriever` and `MultiQueryRetriever`.
- [ai-service-python/app/rag/pipeline.py](../ai-service-python/app/rag/pipeline.py) — `RAGPipeline` accepts optional `multi_query_retriever`; when present, retrieval goes through it; falls back to plain `hybrid_retriever` otherwise.
- [ai-service-python/app/dependencies.py](../ai-service-python/app/dependencies.py) — `get_query_expander()` (lazily caches on `app.state.query_expander`), `get_multi_query_retriever()` returns `None` when disabled.
- [ai-service-python/app/api/routes/search.py](../ai-service-python/app/api/routes/search.py) — wires `multi_query_retriever` into the route's `RAGPipeline` instance.
- [ai-service-python/app/config.py](../ai-service-python/app/config.py) — `groq_fast_model`, `azure_openai_chat_deployment_fast`, `enable_multi_query`, `multi_query_count`, `query_expansion_timeout_ms`, `query_expansion_cache_size`.

**Audit — deferred:** the spec called for persisting expanded queries to `AiRequest` (new `expanded_queries` JSON column) for retrieval-debug forensics. Not yet implemented. `MultiQueryRetriever.last_expanded_queries` is exposed; the route handler does not yet read it. Track under Open Items; cheap follow-up.

**Verification:** [`MultiQueryRetrieverProbe`](../ai-service-python/app/evals/runner.py) added. Acceptance gates pending goldset sizing.

## Production hardening done alongside Phase 1–3

Discovered while smoke-testing the shipped pipeline. Documented here so the rationale survives:

### System prompt — strict grounding + parseable citation format ✅
The original prompt said *"based ONLY on the provided context documents"* — a soft constraint that LLMs interpret loosely, especially when the retrieved context is partially relevant. Tightened in [pipeline.py:15-39](../ai-service-python/app/rag/pipeline.py#L15-L39) to explicitly:
- Forbid use of training knowledge / inferred regulatory facts (BPF, GMP, ICH, etc.).
- Require an exact abstention sentence in the question's language when context is insufficient (FR / EN / AR).
- Require `[Source N]` inline citations that reference chunk indices present in the context. This format is intentionally machine-parseable for the post-hoc verifier (see Open Items).

### Silent ingest failures — class of bug, not one-offs ⚠️
Two PDFs (`partie_i-chapitre_4frdef.pdf`, `european-regulatory-system-medicines_fr.pdf`) had `Document` rows in SQL but **0 chunks** in `TextSegments` and were absent from FAISS/BM25 — meaning every search that should have hit them returned 0 results from those docs, with no error surfaced to users. Root cause: [DevController.cs:92-95](../backend-dotnet-api/src/Sothema.Compliance.Api/Controllers/DevController.cs#L92-L95) catches AI-service ingest exceptions, writes to `Console.WriteLine`, returns `200 OK`, and commits the `Document` row anyway. Both docs re-ingested manually on 2026-05-10. Tracked under Open Items.

### Citation verification — closed for Deep Analysis ✅
[`_extract_citations()`](../ai-service-python/app/agents/agentic_rag/nodes.py) in the agent's `generate` node parses `[Source N]` references from the LLM answer and cross-checks each `N` against the retrieved `chunk_index` set. Only valid references are surfaced on the response (as `citations: list[CitationDTO]`); invalid ones are silently dropped. Combined with the `verify` node's groundedness score, this gives the platform two independent hallucination signals. **Still open for Fast mode** — the same parser is not yet applied to `/api/search` responses. See Open Items.

### Language detection — tightened during Phase 3 ✅
Initial heuristic (ASCII-letter ratio) mis-classified French as English. Rewrote to: (1) Arabic script dominance → `ar`, (2) any French diacritic → `fr`, (3) stopword vote between FR/EN, (4) FR as tie-break (primary user language). See [`detect_language()`](../ai-service-python/app/agents/agentic_rag/prompts.py).

## Phase 3 — LangGraph Agentic Loop ✅ Shipped (2026-05-11)

**New endpoint:** `POST /api/agentic-search` (parallel to `/api/search`, does not replace it).

**Request:**
```python
class AgenticSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    max_iterations: int = 2
```

**Response:** Same shape as existing `SearchResponse` plus `trace: list[StepLog]` (per-step record for audit) and `groundedness_score: float`.

**State machine** (in [ai-service-python/app/agents/agentic_rag/graph.py](../ai-service-python/app/agents/agentic_rag/graph.py)):

```
   plan ──▶ retrieve ──▶ reflect ──┬── sufficient ──▶ generate ──▶ verify ──▶ END
              ▲                    │                                  │
              │                    └── insufficient ──▶ refine_query ─┘
              │                                              │
              └──────────────────────────────────────────────┘
                            (max 2 loops)
```

- **plan** — `tier="reasoning"` (GPT-5.4 prod / Llama-3.3-70B dev), structured output. Analyzes the query, decides single vs. decomposed retrieval, sets initial sub-queries.
- **retrieve** — calls `hybrid_search` tool internally; for decomposed queries runs sub-queries in parallel and fuses with RRF; reranks; accumulates results in state, dedup by `vector_store_id`. Also rejects sub-queries cosine-similar (>0.95) to prior sub-queries to avoid wasting iterations on duplicates.
- **reflect** — `tier="fast"` (GPT-5.4 mini prod / Llama-3.3-70B dev). Returns `Sufficiency(is_sufficient: bool, missing: list[str])`. If insufficient and budget remains, loops to `refine_query`.
- **refine_query** — `tier="fast"`. Produces a new sub-query targeting the gaps reported by `reflect`.
- **generate** — `tier="reasoning"`. Synthesizes the answer with strict citation requirements (uses the existing system prompt from [pipeline.py:13-16](../ai-service-python/app/rag/pipeline.py#L13-L16) extended with citation rules).
- **verify** — `tier="fast"`. Returns `Groundedness(score: float, ungrounded_claims: list[str])`. Threshold calibrated on goldset (start at 0.7, tune); below threshold → 1 regenerate retry with stricter prompt; still below → return answer with `low_confidence: true` flag.

**Hard limits enforced in `AgentBudget` dataclass in state:**
- `max_iterations = 2` (plan → retrieve → reflect cycles)
- `max_total_llm_calls = 8` (raised from 6: plan + reflect + refine + reflect + generate + verify = 6 happy-path calls; need headroom for the verify-retry without breaching the cap)
- `max_wall_clock_ms = 15000` (Azure-only; revisit at 18000 if verify-retry frequently fires near the cap)

On exhaustion, force `generate` with whatever was retrieved.

**State (TypedDict):**
```python
class AgenticRAGState(TypedDict):
    original_query: str
    sub_queries: list[str]
    retrieved: list[RetrievedSegment]   # accumulated, dedup by vector_store_id
    iterations: int
    budget: AgentBudget
    answer: str
    citations: list[Citation]
    groundedness_score: float
    low_confidence: bool
    trace: list[dict]
```

**Tools** (in [ai-service-python/app/agents/agentic_rag/tools.py](../ai-service-python/app/agents/agentic_rag/tools.py)):
- `hybrid_search(query, top_k=10)` — wraps `EmbeddingService.embed_query` → `HybridRetriever.retrieve` → `CrossEncoderReranker.rerank`. The single retrieval primitive the agent calls. **Implementation note:** intentionally does NOT run multi-query expansion inside. The agent's `plan` node already decomposes the user question into focused sub-queries; running multi-query rephrasing on top would double-expand and burn budget for little additional recall.
- `expand_query(query, n=3)` — Phase 2's `QueryExpander`. **Not currently invoked from any node.** The `plan` node does conceptual decomposition (sub-questions about different aspects) rather than rephrasing — keeps things deterministic. Tool is wired in for future use; remove or invoke if planner shows recall issues on short keyword queries.
- `get_neighbors(vector_store_id, before=1, after=1)` — fetch adjacent chunks in the same document via the new `TextSegmentRepository.get_neighbors_by_vector_store_id`. Available; not invoked from any current node — reserved for follow-up if generate runs into partial-chunk truncation issues.
- `lookup_document(document_id)` — returns title, file type, chunk count. Available; not invoked from any current node.

Reranking is **always** called inside `hybrid_search`, never exposed as a tool the LLM picks — optionality there is a footgun.

**Files added (Python):**
- [ai-service-python/app/agents/agentic_rag/__init__.py](../ai-service-python/app/agents/agentic_rag/__init__.py) — re-exports `build_agentic_rag_graph`, `AgenticRAGState`, `Citation`, `StepLog`
- [ai-service-python/app/agents/agentic_rag/state.py](../ai-service-python/app/agents/agentic_rag/state.py) — `AgenticRAGState` TypedDict + `Citation` + `StepLog` dataclasses
- [ai-service-python/app/agents/agentic_rag/budget.py](../ai-service-python/app/agents/agentic_rag/budget.py) — `AgentBudget` with wall-clock / iteration / LLM-call caps
- [ai-service-python/app/agents/agentic_rag/tools.py](../ai-service-python/app/agents/agentic_rag/tools.py) — `hybrid_search`, `get_neighbors`, `lookup_document`
- [ai-service-python/app/agents/agentic_rag/nodes.py](../ai-service-python/app/agents/agentic_rag/nodes.py) — 6 nodes via `make_X_node(ctx)` factory pattern; routers (`route_after_reflect`, `route_after_verify`); inline `_extract_citations` parses `[Source N]` against the retrieved set
- [ai-service-python/app/agents/agentic_rag/graph.py](../ai-service-python/app/agents/agentic_rag/graph.py) — `build_agentic_rag_graph(ctx)` compiles the StateGraph
- [ai-service-python/app/agents/agentic_rag/prompts.py](../ai-service-python/app/agents/agentic_rag/prompts.py) — FR / EN / AR system prompts for `plan`; shared EN prompts for `reflect` / `refine_query` / `verify`. **Language detector** (`detect_language`) uses FR-diacritic + stopword-vote heuristic; defaults to FR on ties (primary user language). Was tightened during smoke test — initial ASCII-ratio heuristic mis-detected French as English.
- [ai-service-python/app/api/routes/agentic_search.py](../ai-service-python/app/api/routes/agentic_search.py) — `POST /api/agentic-search` route; rebuilds the graph per request (closures bind to per-request `RunContext`; compile is structural and cheap)
- [ai-service-python/app/api/schemas/agentic_search.py](../ai-service-python/app/api/schemas/agentic_search.py) — `AgenticSearchRequest`, `AgenticSearchResponse`, `CitationDTO`, `StepLogDTO`

**Files modified (Python):**
- [ai-service-python/app/db/repositories.py](../ai-service-python/app/db/repositories.py) — added `TextSegmentRepository.get_neighbors_by_vector_store_id(vs_id, before, after)`.
- [ai-service-python/app/main.py](../ai-service-python/app/main.py) — registers the new router under `verify_api_key`.
- [ai-service-python/app/config.py](../ai-service-python/app/config.py) — `agent_max_iterations`, `agent_max_llm_calls`, `agent_max_wall_clock_ms`, `agent_groundedness_threshold`.
- Tier abstraction in [ai-service-python/app/services/llm.py](../ai-service-python/app/services/llm.py) was already shipped with Phase 2; no further changes here.
- `AiRequest` cost-logging columns: **deferred** (still no Azure spend to track in dev). Tracked under Open Items.

**Bug surfaced during implementation:** `state.py` had `TYPE_CHECKING`-guarded imports for `RetrievedSegment` / `TextSegment` / `AgentBudget`. LangGraph evaluates the state TypedDict's annotations at runtime via `get_type_hints`, which can't resolve `TYPE_CHECKING`-guarded names. Lifted the imports to module top-level — no circular-import issues because `budget.py` has no upstream deps.

**Backend pass-through (.NET):**
- [Sothema.Compliance.Application/DTOs/AiServiceDtos.cs](../backend-dotnet-api/src/Sothema.Compliance.Application/DTOs/AiServiceDtos.cs) — added `AiAgenticSearchResponseDto`, `AiCitationDto`, `AiStepLogDto`.
- [Sothema.Compliance.Application/Common/Interfaces/IAiService.cs](../backend-dotnet-api/src/Sothema.Compliance.Application/Common/Interfaces/IAiService.cs) — added `AgenticSearchAsync(query, topK, maxIterations, ct)`.
- [Sothema.Compliance.Infrastructure/Services/AiServiceClient.cs](../backend-dotnet-api/src/Sothema.Compliance.Infrastructure/Services/AiServiceClient.cs) — `AgenticSearchAsync` implementation. Uses a linked `CancellationTokenSource` with a **20s deadline** (Python agent has a 15s internal wall-clock cap; 5s buffer for the abstention payload to come back on internal timeout).
- [Sothema.Compliance.Api/Controllers/SearchController.cs](../backend-dotnet-api/src/Sothema.Compliance.Api/Controllers/SearchController.cs) — `POST /api/search/agentic` action. Audit row `Action="DeepAnalysisQuery"`; `Details` JSON includes `iterations`, `llm_calls`, `elapsed_ms`, `groundedness_score`, `low_confidence`, `citations` count, `sub_queries`.

**Frontend (three-mode UX):**
- [frontend-web/src/types/chat.ts](../frontend-web/src/types/chat.ts) — added `DeepAnalysisMeta`, `ChatCitation`; `ChatMessage.deepAnalysis?: DeepAnalysisMeta`.
- [frontend-web/src/services/chatService.ts](../frontend-web/src/services/chatService.ts) — `queryDeepAnalysis(question)` calling `/api/search/agentic`; existing `queryCompliance()` unchanged (still serves Fast and Sources-Only modes).
- [frontend-web/src/pages/Chat.tsx](../frontend-web/src/pages/Chat.tsx) — mode toggle now has 3 pills: **Fast** (default) / **Deep Analysis** / **Sources only**. **Sources only** stays user-visible for now per user preference (Phase 3 plan said gate behind dev flag — deferred). **Loading state for Deep is an honest spinner with elapsed-seconds counter** ("Analyzing… 4.2s"), not a fake-progress trace replay — user picked "honest spinner" over the original plan's trace-replay design. On response, renders a **groundedness badge** (green ≥70%, amber otherwise) plus iteration/LLM-call/elapsed chips, and an **amber low-confidence banner** above the answer when `low_confidence=true`.

## Phase 3 hardening (2026-05-14)

Shipped after real-world testing surfaced two failure classes the original Phase 3 missed: (1) over-eager abstention on comparative/multi-hop queries (the strict generate prompt told the LLM to abstain whenever no single chunk fully answered, which is structurally true for any question whose answer must be assembled across chunks); (2) silent-zero groundedness scores when Groq rate-limited the verify call (`content or "{}"` substitution in [`llm.py`](../ai-service-python/app/services/llm.py) made Pydantic-defaulted `Groundedness(score=0.0)` indistinguishable from a real zero).

**1. Plan-aware complexity routing.** Plan's `len(sub_queries)` is now the single complexity signal that three nodes coordinate on:

| `len(sub_queries)` | route_after_retrieve | generate prompt | verify threshold |
|---|---|---|---|
| 1 (single_pass) | reflect only if `<3` chunks retrieved | `GENERATE_SYSTEM` (strict) | 0.75 |
| ≥2 (multi_pass) | **skip reflect/refine → generate** | `GENERATE_SYSTEM_SYNTHESIS` | **0.40** |

New `route_after_retrieve` in [nodes.py](../ai-service-python/app/agents/agentic_rag/nodes.py) handles all three rules. The multi_pass bypass eliminates the reflect/refine loop that was burning 4 LLM calls and ~25s wall-clock on comparative queries before generate could run — measured savings: 38s → 10s on the same query.

**2. `GENERATE_SYSTEM_SYNTHESIS` prompt** ([prompts.py](../ai-service-python/app/agents/agentic_rag/prompts.py)). Keeps the no-external-knowledge rule, but explicitly permits combining facts across chunks and reserves abstention for *topic absent from all chunks* — not "no single chunk fully answers." Selected by generate when `len(sub_queries) >= 2`. Trace records `mode=synthesis|strict` per call.

**3. Permissive verify prompt for synthesis.** `VERIFY_SYSTEM` now lists four grounded-claim patterns: verbatim, direct implication, **synthesis across multiple sources**, and logical aggregation. Closing line shifted from "be conservative" to "be charitable on synthesis." Also includes a note that `[Source N]` and `[Source: <title>, Chunk N]` are equivalent (the LLM occasionally copies the latter from `_build_generate_context` headers).

**4. Rate-limit-aware verify.** Wraps the verify LLM call in tenacity (3 attempts, `wait_exponential(min=2, max=10)`, retry-filter on rate-limit/timeout/connection errors). On final exhaustion or non-retryable failure: returns sentinel `groundedness_score=-1.0`, `low_confidence=True`, populates a new `verification_error: str` field — and **keeps the generated answer**. Old behavior: silent `score=0.0` indistinguishable from a real zero, sometimes flipping the answer to abstention path. New `_is_service_error` helper detects rate limits both via SDK exception types (`openai.RateLimitError`, `APITimeoutError`, `APIConnectionError`) and via wrapped-`LLMError` message sniffing.

**5. LLM-service empty-body detection.** [llm.py](../ai-service-python/app/services/llm.py) `generate_structured` no longer substitutes `"{}"` for empty bodies. When Groq returns 200 with empty/whitespace/`{}`/`[]` content (typical during rate-throttling), the service raises `LLMError` with the completion-token count attached, triggering retry through its 3× backoff loop. Closes the silent-zero groundedness class of bug.

**6. Post-parse validation in verify.** Even if Groq returns parseable but malformed JSON (e.g. `score` as a string, `ungrounded_claims` as null), verify now range-checks `score ∈ [0.0, 1.0]` and type-checks `ungrounded_claims` as a list. Violations raise `LLMError` → land in the sentinel branch instead of surfacing a fake score.

**7. Citation extractor robustness.** `_extract_citations` accepts both the canonical `[Source N]` form and the header-style `[Source: <title>, Chunk N]` / `[Chunk N]` forms the LLM sometimes emits. Both regexes run on every answer; dedup by `chunk_index` handles mixed-format outputs.

**8. Budget hardening (option A+B from triage).** Three changes:
- `AgentBudget.can_afford_llm_call(reserve=0)` — `reserve` lets a node assert "after my call, N more slots must still exist." Reflect and refine call with `reserve=2` so generate + verify always have budget.
- `agent_max_wall_clock_ms`: **15000 → 25000** ([config.py](../ai-service-python/app/config.py)). Groq's internal retries on rate-limit can chew 5–10s per call.
- **Generate uses slot-only check** (`llm_calls_made >= max_total_llm_calls`), not the combined wall-clock-aware `can_afford_llm_call()`. Single most-important node in the graph; guaranteed one attempt regardless of elapsed time, since slot-count is the only true ceiling. Trace token changed from `budget_exhausted` to `slots_exhausted` for diagnostic clarity.

**9. Reflect chunk window matches verify.** `_summarize_chunks_for_judge` default was 250 chars; reflect was wrongly returning `is_sufficient=False` whenever the answer-bearing sentence sat past char 250. Reflect now explicitly passes `max_chars=1500` (verify already passed `2000` for the same reason). Only relevant when reflect actually runs (single_pass with <3 chunks); inert on the new multi_pass bypass path.

**10. Frontend "Not verified" UX.** [Chat.tsx](../frontend-web/src/pages/Chat.tsx) handles `groundednessScore < 0` (the -1.0 sentinel) — banner now reads "Answer not verified — verifier could not run, review citations carefully" and the badge renders slate-gray "Not verified" instead of "-100% grounded". Treats any negative value, not just exactly -1, so future sentinels keep working.

**State additions** ([state.py](../ai-service-python/app/agents/agentic_rag/state.py)):
- `verification_error: str | None` — populated when verify falls into the sentinel path; surfaced on `AgenticSearchResponse.verification_error`.
- `groundedness_score` semantics: `-1.0` = not verified (service error), `0.0–1.0` = real score. Documented inline.

**New dependency:** `tenacity==9.1.2` in [requirements.txt](../ai-service-python/requirements.txt).

**End-to-end validation (paid-tier Groq, 2026-05-14):**

| Query | type | mode | iter | LLM calls | grounded | low_conf | citations | elapsed |
|---|---|---|---|---|---|---|---|---|
| `durée minimale conservation dossiers de lot BPF` | varies | varies | 0 | 3 | 1.00 | False | 1 | ~6–9s |
| `comparer les exigences de stockage entre les établissements pharmaceutiques marocains et les BPF européennes` | multi_pass | synthesis | 0 | 3 | 0.90 | False | 3 | ~10s |

Rate-limit path verified earlier in the day under free-tier quota exhaustion: sentinel `-1.0` returned, answer preserved, `verification_error` populated with the verbatim Groq error, frontend shows "Not verified" badge correctly. No crashes, no infinite retry loops.

## Reuse Map (existing primitives wired into the agent)

| Tool / node | Reuses |
|---|---|
| `hybrid_search` | [HybridRetriever.retrieve()](../ai-service-python/app/rag/hybrid_retriever.py#L33) + [EmbeddingService.embed_query()](../ai-service-python/app/services/embedding.py) + new `CrossEncoderReranker` |
| `expand_query` | new `QueryExpander` (Phase 2) + [LLMService.generate()](../ai-service-python/app/services/llm.py) |
| `get_neighbors` | [TextSegmentRepository](../ai-service-python/app/db/repositories.py) (new method) |
| `lookup_document` | [DocumentRepository](../ai-service-python/app/db/repositories.py) |
| `plan` / `generate` | [LLMService.generate()](../ai-service-python/app/services/llm.py) with `tier="reasoning"` → GPT-5.4 in prod, Llama-3.3-70B in dev |
| `reflect` / `verify` / `refine_query` / `expand_query` | [LLMService.generate()](../ai-service-python/app/services/llm.py) with `tier="fast"` → GPT-5.4 mini in prod, Llama-3.3-70B in dev |
| Audit | existing `AiRequest` / `AiRequestSegment` tables (extended with token/cost/provider/model columns); SearchController audit-log pattern |

## Evaluation

Extend [ai-service-python/app/evals/](../ai-service-python/app/evals/):

- **Existing metrics (recall@10, MRR@10, nDCG@10):** run after each phase. Phase 1 must show recall@10 +5%+; Phase 2 must show non-regression on Phase 1 baseline + ideally +3% more. Retrieval metrics are model-independent — dev numbers (Groq) transfer to prod (Azure).
- **New: `app/evals/faithfulness.py`** — LLM-as-judge. In prod, judge = GPT-5.4 mini judging GPT-5.4 outputs (same vendor, smaller model — partial self-bias mitigation). In dev, judge = Llama-3.3-70B judging itself (full self-bias; treat as smoke test, not load-bearing). Returns `FaithfulnessJudgment(supported_claims, total_claims, unsupported)`. Score = supported / total.
- **New: `app/evals/agentic_runner.py`** — runs the full agent over the goldset; captures retrieval metrics, faithfulness score, mean iterations, mean LLM calls, p95 latency, **per-query token counts and estimated cost**. Phase 3 acceptance (measured on Azure post-credentials): faithfulness +15%+ on multi-hop queries vs. Phase 2 baseline; p95 latency under 15s. Dev runs prove the pipeline executes; **acceptance gates only fire post-Azure-swap**.

**End-to-end manual verification per phase:**
1. `docker-compose up` from [docker/](../docker/).
2. Run a known French regulatory question (e.g., "Quelles sont les exigences de qualification du personnel pour la libération des lots selon les BPF ?") via the new endpoint, then via the legacy endpoint, and compare answer + sources.
3. Run a deliberately multi-hop question requiring information from two different documents — confirm the agent's `trace` shows >1 retrieval step.
4. Force a knowledge gap (ask something the corpus doesn't cover) — confirm the agent says so cleanly rather than hallucinating, and `groundedness_score` is low.
5. `pytest ai-service-python/tests/` — confirm no regressions in existing tests.
6. Run the eval runner on the goldset — record before/after numbers in commit message.

## Rollout Order

1. Phase 1 in isolation (PR 1) — reranker + eval delta. Ships independently.
2. Phase 2 in isolation (PR 2) — multi-query rewriter. Ships independently. Both phases benefit `/api/search` immediately.
3. Phase 3 (PR 3) — new endpoint, agent loop, frontend toggle, .NET pass-through.

Each PR is independently revertable. Phase 3 does not modify the existing `/api/search` code path.

## Anti-Recommendations

1. **Don't replace the `/api/analyze` LangGraph DAG.** It's deterministic by design (compliance audit trail) — agentic non-determinism would break audit guarantees regulators expect.
2. **Don't switch the prod LLM provider away from Azure OpenAI.** Pharmaceutical compliance + data residency = Azure-only in prod. Groq is dev-only.
3. **Don't hardcode model names at call sites.** Always go through the `tier="reasoning" | "fast"` abstraction so swapping providers (or upgrading models) is a config change.
4. **Don't treat dev (Groq) eval numbers as load-bearing.** Faithfulness, agent iteration counts, and groundedness thresholds will all shift on Azure. Re-run on Azure before declaring acceptance.
5. **Don't use HyDE for query expansion** — fabricated regulatory terminology poisons retrieval.
6. **Don't expose `rerank` as a tool the LLM picks** — wrap it inside `hybrid_search` so it always happens.
7. **Don't migrate FAISS to a different index** (HNSW, IVFPQ) yet. Reranking + multi-query are bigger wins; revisit if corpus exceeds ~500k chunks.
8. **Don't allow infinite loops** — iteration counter lives in `AgentBudget`, not in any LLM-controlled field.
9. **Don't ship streaming this round.** Streaming a non-streaming agent (which makes blocking LLM and tool calls) gives little value vs. cost; revisit when conversation memory is added.
10. **Don't drop Phase 2 from Fast mode to "save latency."** On a precision-critical compliance product, recall floor matters more than latency ceiling — a missed clause is worse than a 3s wait. Use parallel execution + cache + timeout fallback to keep Fast fast.

## Deferred (future rounds)

- **Conversation memory (Phase 4)** — when added, store in SQL Server with .NET-owned `Conversations` / `ConversationMessages` tables. Python receives `history` in request payload, never reads/writes the conversation tables. Matches existing audit pattern.
- **Streaming (Phase 5)** — SSE from FastAPI via LangGraph `astream_events` → ASP.NET passthrough → React `EventSource`. Defer until conversation memory lands.
- **Permission filtering** — design ready: thread `allowed_doc_ids` through the `hybrid_search` tool via a `contextvars.ContextVar` set in the route handler so the LLM never sees the allowlist (prompt-injection safe).

## Open Items

### Carried over (still applicable to Phase 3)
- **Goldset size:** still gating Phase 1+2 acceptance. Probes are wired in; nobody has run them yet because per-phase recall/nDCG deltas on <30 queries are noise. Expand the goldset before quoting any retrieval metric.
- **Azure OpenAI credentials:** required before prod rollout. Until then, all dev runs on Groq Llama-3.3-70B. Plan acceptance gates (faithfulness +15%, p95 <15s) only fire after Azure swap.
- **Cost ceiling on Azure:** define a per-day / per-user spend cap once GPT-5.4 is wired in. Audit columns (`total_input_tokens`, `total_output_tokens`, `estimated_cost_usd`, `provider`, `model`) on `AiRequest` are spec'd in Phase 3 but not yet added.
- **Groundedness threshold:** ✅ **Replaced by per-query tiered thresholds** (0.75 single_pass / 0.40 multi_pass) in the Phase 3 hardening pass. Recalibrate both on the goldset post-Azure.

### New (surfaced during Phase 1+2 implementation)
- **Reranker model is a CPU-vs-quality compromise.** Currently `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`. If prod deploys to GPU or a beefy server CPU, swap back to `BAAI/bge-reranker-v2-m3` for ~10–20% better top-1 precision on multilingual content — single env-var change (`AI_SERVICE_RERANKER_MODEL`).
- **Expanded-query audit logging.** `MultiQueryRetriever.last_expanded_queries` is exposed but not persisted. Add a JSON column to `AiRequest` and have the search route read+write it. Cheap follow-up; gives FR/AR/EN drift visibility.
- **Silent ingest failure class of bug.** [DevController.cs:92-95](../backend-dotnet-api/src/Sothema.Compliance.Api/Controllers/DevController.cs#L92-L95) catches AI-ingest exceptions and returns 200. Same swallowed-failure pattern likely exists on the SharePoint sync ingest path (the two re-ingested docs came via SharePoint, not dev upload). Two fixes either-or:
  - Add an `IngestionStatus` column to `Document` (`Pending` / `Indexed` / `Failed`) and surface in the Documents UI.
  - Or treat AI-ingest failure as a hard upload failure (rollback the `Document` row).
  Pick one before more docs slip through.
- **Citation verification.** ✅ **Closed by Phase 3.** `_extract_citations()` in [nodes.py](../ai-service-python/app/agents/agentic_rag/nodes.py) parses `[Source N]` from the answer and cross-checks against the retrieved chunk-index set. Only valid citations are returned on the agent response; invalid ones are silently dropped. **Follow-up worth doing:** also surface the parser on the Fast-mode path (`/api/search`) for symmetry — currently the strict-grounding prompt asks for `[Source N]` but nobody validates them there. ~30 LoC; same parser, different call site.
- **Bug visible during testing: Fast-mode latency on Docker-for-Mac is ~5.4s, over the 3s SLA target.** Acceptable for now (CPU constraint, not architecture). Re-measure after deploying to prod-class hardware before declaring SLA compliance.

### New (surfaced during Phase 3 implementation)
- **Sources-only mode still user-visible.** Plan said gate it behind a dev flag. Deferred per explicit user preference during shipping. Revisit before opening to non-technical users.
- **`expand_query` / `get_neighbors` / `lookup_document` tools are wired but unused.** All three are imported and importable from `tools.py` but no agent node currently calls them. Either prune them or invoke from `plan` / `generate` once eval shows recall or truncation gaps. Carrying unused code is a maintenance tax; carrying *removed* primitives we'd then need to rebuild is worse — leaning toward keep-and-document.
- **Per-request graph compilation.** [agentic_search.py](../ai-service-python/app/api/routes/agentic_search.py) rebuilds the LangGraph state machine on every request (cheap — structural only, no model loading). If profile data shows it matters in prod, swap to a process-level compiled graph with a `contextvars.ContextVar` for per-request `RunContext` injection. Not a current bottleneck.
- **Refine-loop / verify-retry not yet observed in practice.** Smoke-test queries all completed in iteration 0 with groundedness 1.0 — happy path only. Need a multi-hop test set to exercise the refine loop, and a deliberately ungrounded prompt to exercise verify-retry. Eval goldset gating still applies.

### New (surfaced during Phase 3 hardening — 2026-05-14)
- **Reflect/refine path is now mostly dead code.** Post-hardening, `route_after_retrieve` only sends traffic to reflect when single_pass + `chunk_count < 3` — a rare path. Refine is reachable only via reflect. Leaving in place because (a) it's the safety net when retrieval genuinely underperforms, (b) tearing it out before goldset eval would be premature. Revisit after 4–6 weeks of prod logs.
- **Plan classification is LLM-stochastic.** Same query classified `single_pass` and `multi_pass` on consecutive runs ("durée minimale conservation dossiers de lot BPF" → 1 sub-query then 3 sub-queries). Working as intended (LLM judgment), but worth tracking in audit logs to see how often it flips. If we ever want deterministic routing, add a heuristic prefilter on question words ("compare", "différence", "vs", "et … et …").
- **Tenacity outer-retry on verify can blow the wall clock.** Worst case: 3× tenacity attempts × ~8s each = 24s, on top of plan+generate. The new 25s wall-clock is too tight for the verify path if generate already ate 10s. Mitigations applied: generate ignores wall-clock; verify's failure path returns the sentinel cleanly. Worst case still: "no verify result, answer kept, frontend shows Not verified" — which is the desired graceful degradation.
- **Groq paid tier still has TPD ceilings.** Confirmed during testing: free tier = 100k TPD on llama-3.3-70b-versatile; paid tier higher but not unlimited. Worth documenting in [credentials-setup-guide.md](credentials-setup-guide.md) and surfacing in oncall runbooks when written.
