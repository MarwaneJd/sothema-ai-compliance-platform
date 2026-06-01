"""Six agent nodes for the LangGraph state machine.

Each node is an async function `node(state) -> dict` returning partial state
updates that LangGraph merges into the live state. Nodes receive their
collaborators (LLM, retriever, segment repo, reranker) via a `RunContext`
dataclass passed at graph-build time — keeping node signatures pure for testing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.agents.agentic_rag.budget import AgentBudget
from app.agents.agentic_rag.prompts import (
    GENERATE_RETRY_SUFFIX,
    GENERATE_SYSTEM,
    GENERATE_SYSTEM_SYNTHESIS,
    PLAN_SYSTEM_AR,
    PLAN_SYSTEM_EN,
    PLAN_SYSTEM_FR,
    REFINE_SYSTEM,
    REFLECT_SYSTEM,
    VERIFY_SYSTEM,
    detect_language,
)
from app.agents.agentic_rag.state import AgenticRAGState, Citation, StepLog
from app.agents.agentic_rag.tools import hybrid_search
from app.core.exceptions import LLMError
from app.db.repositories import TextSegmentRepository
from app.rag.hybrid_retriever import HybridRetriever, RetrievedSegment
from app.rag.reranker import CrossEncoderReranker
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService

if TYPE_CHECKING:
    from app.db.models import TextSegment

logger = structlog.get_logger()


# ─── Run context ───────────────────────────────────────────────────────────────


@dataclass
class RunContext:
    """Per-request collaborators. Passed to each node via a closure."""

    llm: LLMService
    hybrid_retriever: HybridRetriever
    embedding_service: EmbeddingService
    segment_repo: TextSegmentRepository
    reranker: CrossEncoderReranker | None
    reranker_fetch_multiplier: int
    groundedness_threshold: float = 0.7


# ─── Structured outputs ────────────────────────────────────────────────────────


class PlanResult(BaseModel):
    sub_queries: list[str] = Field(default_factory=list)


class Sufficiency(BaseModel):
    is_sufficient: bool = False
    missing: list[str] = Field(default_factory=list)


class RefinedQuery(BaseModel):
    sub_query: str = ""


class Groundedness(BaseModel):
    score: float = 0.0
    ungrounded_claims: list[str] = Field(default_factory=list)


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _ensure_budget(state: AgenticRAGState) -> AgentBudget:
    budget = state.get("budget")
    if budget is None:
        budget = AgentBudget()
    return budget


def _append_trace(
    state: AgenticRAGState, step: str, budget: AgentBudget, detail: str = ""
) -> list[StepLog]:
    trace = list(state.get("trace", []))
    trace.append(
        StepLog(
            step=step,
            iteration=state.get("iterations", 0),
            elapsed_ms=budget.elapsed_ms(),
            detail=detail,
        )
    )
    return trace


def _plan_system_prompt(language: str) -> str:
    return {
        "ar": PLAN_SYSTEM_AR,
        "en": PLAN_SYSTEM_EN,
    }.get(language, PLAN_SYSTEM_FR)


def _summarize_chunks_for_judge(segments: list["TextSegment"], max_chars: int = 250) -> str:
    lines: list[str] = []
    for seg in segments:
        title = seg.document.Title if seg.document else "Unknown"
        snippet = (seg.Content or "")[:max_chars].replace("\n", " ")
        lines.append(f"[Source {seg.ChunkIndex}] {title}: {snippet}")
    return "\n".join(lines)


def _build_generate_context(segments: list["TextSegment"]) -> str:
    parts: list[str] = []
    for seg in segments:
        title = seg.document.Title if seg.document else "Unknown"
        parts.append(
            f"[Source: {title}, Chunk {seg.ChunkIndex}]\n{seg.Content}"
        )
    return "\n\n---\n\n".join(parts)


def _dedup_into_state(
    state: AgenticRAGState,
    new_retrieved: list[RetrievedSegment],
    new_segments: list["TextSegment"],
) -> tuple[list[RetrievedSegment], dict[str, "TextSegment"]]:
    """Merge fresh retrieval into the accumulator, dedup by vector_store_id."""
    retrieved = list(state.get("retrieved", []))
    segments_by_id = dict(state.get("segments_by_id", {}))
    seen = {r.vector_store_id for r in retrieved}
    for r, seg in zip(new_retrieved, new_segments, strict=False):
        if r.vector_store_id in seen:
            continue
        seen.add(r.vector_store_id)
        retrieved.append(r)
        if seg.VectorStoreId:
            segments_by_id[seg.VectorStoreId] = seg
    return retrieved, segments_by_id


def _select_context_segments(
    state: AgenticRAGState, top_k: int
) -> list["TextSegment"]:
    """Pick the segments fed to `generate`. Preserves first-seen order — that's
    rerank order from each sub-query retrieval. Good enough; reranking the
    union against the original query is an option if quality slips."""
    retrieved = state.get("retrieved", [])
    seg_by_id = state.get("segments_by_id", {})
    out: list["TextSegment"] = []
    for r in retrieved[:top_k]:
        seg = seg_by_id.get(r.vector_store_id)
        if seg is not None:
            out.append(seg)
    return out


# Strict canonical form: [Source 5] or [Source 3, Source 7].
_CITATION_RE_STRICT = re.compile(
    r"\[Source\s+(\d+(?:\s*,\s*Source\s+\d+)*)\s*\]", re.IGNORECASE
)
# Tolerant fallback: matches header-style citations the LLM sometimes copies
# from _build_generate_context, e.g. "[Source: foo.pdf, Chunk 5]" or
# "[Chunk 5]". Captures the integer after "Chunk". Only used when the strict
# parser found no citations — we still prefer the canonical form.
_CITATION_RE_HEADER = re.compile(
    r"\[(?:Source[^,\]]*,\s*)?Chunk\s+(\d+)\s*\]", re.IGNORECASE
)


def _extract_citations(answer: str, context_segments: list["TextSegment"]) -> list[Citation]:
    """Parse citation references from the answer; keep only valid ones.

    Accepts two formats so a stylistic slip from the LLM doesn't drop all
    citations and silently tank groundedness:
      • Canonical:   "[Source 5]" / "[Source 3, Source 7]"
      • Header-style fallback: "[Source: filename, Chunk 5]" / "[Chunk 5]"

    Used for both audit (return on the API) and downstream observability —
    invalid citations are a hallucination signal."""
    valid_by_chunk_idx: dict[int, "TextSegment"] = {
        seg.ChunkIndex: seg for seg in context_segments
    }
    citations: list[Citation] = []
    seen_indices: set[int] = set()

    def _add(idx: int) -> None:
        if idx in seen_indices:
            return
        seg = valid_by_chunk_idx.get(idx)
        if seg is None:
            return
        seen_indices.add(idx)
        citations.append(
            Citation(
                source_index=idx,
                document_id=str(seg.DocumentId),
                document_title=seg.document.Title if seg.document else "Unknown",
                chunk_index=seg.ChunkIndex,
                vector_store_id=seg.VectorStoreId or "",
            )
        )

    # Strict canonical form. Always runs.
    for match in _CITATION_RE_STRICT.finditer(answer):
        for n in re.findall(r"\d+", match.group(1)):
            _add(int(n))

    # Header-style fallback. Also always runs — _add dedups by chunk index so
    # mixing both forms in one answer is safe.
    for match in _CITATION_RE_HEADER.finditer(answer):
        _add(int(match.group(1)))

    return citations


# ─── Nodes ─────────────────────────────────────────────────────────────────────


def make_plan_node(ctx: RunContext):
    async def plan(state: AgenticRAGState) -> dict:
        budget = _ensure_budget(state)
        query = state["original_query"]
        language = detect_language(query)

        if not budget.can_afford_llm_call():
            # Degenerate: fall through to retrieve with the raw query.
            return {
                "language": language,
                "sub_queries": [query],
                "budget": budget,
                "iterations": 0,
                "trace": _append_trace(state, "plan", budget, "budget_exhausted_at_entry"),
            }

        messages = [
            {"role": "system", "content": _plan_system_prompt(language)},
            {"role": "user", "content": query},
        ]
        try:
            result = await ctx.llm.generate_structured(
                messages=messages,
                response_format=PlanResult,
                tier="reasoning",
                temperature=0.1,
                max_tokens=512,
            )
            budget.record_llm_call()
            sub_queries = [
                q.strip() for q in (result.sub_queries or []) if q and q.strip()
            ] or [query]
        except Exception as e:
            logger.warning("Plan failed, falling back to raw query", error=str(e)[:200])
            sub_queries = [query]

        sub_queries = sub_queries[:3]
        query_type = "single_pass" if len(sub_queries) == 1 else "multi_pass"
        logger.info(
            "PLAN node output",
            original_query=query,
            language=language,
            query_type=query_type,
            sub_query_count=len(sub_queries),
            sub_queries=sub_queries,
        )
        return {
            "language": language,
            "sub_queries": sub_queries,
            "budget": budget,
            "iterations": 0,
            "trace": _append_trace(
                state,
                "plan",
                budget,
                f"sub_queries={len(sub_queries)} type={query_type} lang={language}",
            ),
        }

    return plan


def make_retrieve_node(ctx: RunContext):
    async def retrieve(state: AgenticRAGState) -> dict:
        budget = _ensure_budget(state)
        top_k = state.get("top_k", 10)
        existing = state.get("sub_queries", [])
        already_retrieved = {r.vector_store_id for r in state.get("retrieved", [])}

        # Identify the sub-queries we have not yet retrieved against. Stored
        # alongside each retrieval call's results so refine_query iterations
        # don't re-run the original queries.
        executed_qs = state.get("executed_sub_queries", [])
        new_qs = [q for q in existing if q not in executed_qs]

        if not new_qs:
            return {
                "trace": _append_trace(
                    state, "retrieve", budget, "no_new_sub_queries"
                ),
            }

        # Sequential, not parallel: each hybrid_search hits the DB via
        # `segment_repo.get_by_vector_store_ids` on a single shared AsyncSession.
        # pyodbc / ODBC Driver 18 reject concurrent statements on one connection
        # with `HY000 Connection is busy with results for another command`. The
        # FAISS + BM25 + rerank parts are CPU-bound on the same process anyway,
        # so we'd serialize on the GIL even if we tried — running these in a
        # `gather` only bought us the connection-busy bug. 2–3 sub-queries × ~50ms
        # DB time = ~150ms total, well inside the 15s budget.
        all_retrieved: list[RetrievedSegment] = []
        all_segments: list[TextSegment] = []
        for q in new_qs:
            r = await hybrid_search(
                query=q,
                top_k=top_k,
                hybrid_retriever=ctx.hybrid_retriever,
                embedding_service=ctx.embedding_service,
                segment_repo=ctx.segment_repo,
                reranker=ctx.reranker,
                reranker_fetch_multiplier=ctx.reranker_fetch_multiplier,
            )
            all_retrieved.extend(r.retrieved)
            all_segments.extend(r.segments)

        merged_retrieved, merged_segments_by_id = _dedup_into_state(
            state, all_retrieved, all_segments
        )
        added = len(merged_retrieved) - len(already_retrieved)

        return {
            "retrieved": merged_retrieved,
            "segments_by_id": merged_segments_by_id,
            "executed_sub_queries": [*executed_qs, *new_qs],
            "trace": _append_trace(
                state, "retrieve", budget, f"new_qs={len(new_qs)} +chunks={added}"
            ),
        }

    return retrieve


def make_reflect_node(ctx: RunContext):
    async def reflect(state: AgenticRAGState) -> dict:
        budget = _ensure_budget(state)

        # Reserve 2 slots for generate + verify so we never starve them.
        # If we cannot afford another LLM call OR we're at iteration cap,
        # short-circuit to "sufficient" so the graph proceeds to generate.
        if not budget.can_afford_llm_call(reserve=2) or budget.is_exhausted(state.get("iterations", 0)):
            return {
                "is_sufficient": True,
                "missing": [],
                "trace": _append_trace(
                    state, "reflect", budget, "budget_exhausted_short_circuit"
                ),
            }

        segments = list(state.get("segments_by_id", {}).values())
        if not segments:
            return {
                "is_sufficient": False,
                "missing": ["aucun document récupéré"],
                "trace": _append_trace(state, "reflect", budget, "no_segments"),
            }

        # Use 1500 chars (vs the 250-char default) so the judge can see evidence
        # past the chunk preview. Reflect was returning is_sufficient=False on
        # queries whose answer sat past char 250 — same failure mode verify hit.
        chunks_summary = _summarize_chunks_for_judge(segments, max_chars=1500)
        user_msg = (
            f"Original question: {state['original_query']}\n\n"
            f"Retrieved chunks:\n{chunks_summary}"
        )
        try:
            result = await ctx.llm.generate_structured(
                messages=[
                    {"role": "system", "content": REFLECT_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=Sufficiency,
                tier="fast",
                temperature=0.0,
                max_tokens=512,
            )
            budget.record_llm_call()
            is_sufficient = bool(result.is_sufficient)
            missing = list(result.missing or [])
        except Exception as e:
            logger.warning("Reflect failed, assuming sufficient", error=str(e)[:200])
            is_sufficient = True
            missing = []

        return {
            "is_sufficient": is_sufficient,
            "missing": missing,
            "trace": _append_trace(
                state,
                "reflect",
                budget,
                f"sufficient={is_sufficient} missing={len(missing)}",
            ),
        }

    return reflect


def make_refine_query_node(ctx: RunContext):
    async def refine_query(state: AgenticRAGState) -> dict:
        budget = _ensure_budget(state)
        prior = state.get("sub_queries", [])
        missing = state.get("missing", [])

        # Reserve 2 slots for generate + verify (same as reflect).
        if not budget.can_afford_llm_call(reserve=2) or not missing:
            # No room or nothing to refine on — bump iteration and let reflect short-circuit.
            return {
                "iterations": state.get("iterations", 0) + 1,
                "trace": _append_trace(
                    state, "refine_query", budget, "no_refine_possible"
                ),
            }

        system_prompt = REFINE_SYSTEM.format(
            prior_queries=" | ".join(prior),
            missing_topics=" | ".join(missing),
        )
        try:
            result = await ctx.llm.generate_structured(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": state["original_query"]},
                ],
                response_format=RefinedQuery,
                tier="fast",
                temperature=0.2,
                max_tokens=256,
            )
            budget.record_llm_call()
            new_q = (result.sub_query or "").strip()
        except Exception as e:
            logger.warning("Refine failed", error=str(e)[:200])
            new_q = ""

        if not new_q or new_q.lower() in {q.lower() for q in prior}:
            # No useful refinement — bump iteration anyway so reflect can short-circuit.
            return {
                "iterations": state.get("iterations", 0) + 1,
                "trace": _append_trace(
                    state, "refine_query", budget, "duplicate_or_empty"
                ),
            }

        return {
            "sub_queries": [*prior, new_q],
            "iterations": state.get("iterations", 0) + 1,
            "trace": _append_trace(
                state, "refine_query", budget, f"new_q={new_q[:80]}"
            ),
        }

    return refine_query


def make_generate_node(ctx: RunContext):
    async def generate(state: AgenticRAGState) -> dict:
        budget = _ensure_budget(state)
        top_k = state.get("top_k", 10)

        # Acknowledge any retry signal from verify; if we don't clear it here, a
        # skipped verify (budget-exhausted) on the next pass would leave it True
        # and the router would loop back to generate forever.
        clear_pending = {"pending_retry": False}

        # Generate is the load-bearing node: without it the user gets only
        # abstention. Guarantee one attempt as long as we still have an LLM-call
        # slot, even if upstream nodes (esp. plan during a Groq rate-limit
        # storm) chewed the wall clock. Slot exhaustion is still a hard stop —
        # that means callers have made max_total_llm_calls already, which is a
        # real ceiling, not transient elapsed-time slippage.
        if budget.llm_calls_made >= budget.max_total_llm_calls:
            return {
                **clear_pending,
                "answer": _abstention(state.get("language", "fr")),
                "citations": [],
                "trace": _append_trace(state, "generate", budget, "slots_exhausted"),
            }

        context_segments = _select_context_segments(state, top_k)
        if not context_segments:
            return {
                **clear_pending,
                "answer": _abstention(state.get("language", "fr")),
                "citations": [],
                "trace": _append_trace(state, "generate", budget, "no_context"),
            }

        retries = state.get("generate_retries", 0)
        # Pick prompt by query complexity. Single sub-query → strict grounding
        # (Fast-mode parity). Multi sub-query (comparison / multi-hop) → the
        # synthesis prompt that explicitly permits combining facts across
        # chunks and reserves abstention for genuinely-absent topics. Same
        # complexity signal used by _effective_groundedness_threshold and
        # route_after_retrieve, so the three nodes stay coherent.
        sub_queries = state.get("sub_queries", [])
        base_system = (
            GENERATE_SYSTEM_SYNTHESIS if len(sub_queries) >= 2 else GENERATE_SYSTEM
        )
        system = base_system + (GENERATE_RETRY_SUFFIX if retries > 0 else "")
        context = _build_generate_context(context_segments)
        user_msg = (
            f"Context documents:\n\n{context}\n\nQuestion: {state['original_query']}"
        )

        try:
            answer = await ctx.llm.generate(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                tier="reasoning",
                temperature=0.1,
                max_tokens=2048,
            )
            budget.record_llm_call()
        except LLMError as e:
            logger.warning("Generate failed", error=str(e)[:200])
            answer = _abstention(state.get("language", "fr"))

        citations = _extract_citations(answer, context_segments)
        mode = "synthesis" if len(sub_queries) >= 2 else "strict"
        return {
            **clear_pending,
            "answer": answer,
            "citations": citations,
            "trace": _append_trace(
                state,
                "generate",
                budget,
                f"mode={mode} retry={retries} citations={len(citations)}",
            ),
        }

    return generate


_RATE_LIMIT_SIGNALS = ("rate_limit", "rate limit", "429", "too many requests")


def _is_service_error(exc: BaseException) -> bool:
    """True for transient infra errors we should retry (rate limit, timeout, conn).

    The LLM service wraps everything in LLMError(f"...: {original}"), so the
    original exception type is lost — we sniff the message for rate-limit
    signals as a fallback. Direct SDK exceptions are also handled in case they
    leak past the wrapper."""
    if isinstance(exc, RateLimitError | APITimeoutError | APIConnectionError):
        return True
    msg = str(exc).lower()
    return any(sig in msg for sig in _RATE_LIMIT_SIGNALS)


def _effective_groundedness_threshold(state: AgenticRAGState, base: float) -> float:
    """Lower the bar for comparative / multi-hop queries.

    Synthesis answers legitimately combine facts across chunks, so verbatim
    support per sentence is unrealistic. Plan's sub-query count is our cheapest
    complexity signal: 1 sub-query → simple factual (use the strict base ~0.75);
    2+ sub-queries → comparative / multi-hop (relax to ~0.40)."""
    sub_queries = state.get("sub_queries", [])
    if len(sub_queries) >= 2:
        return 0.40
    return base


def make_verify_node(ctx: RunContext):
    async def verify(state: AgenticRAGState) -> dict:
        budget = _ensure_budget(state)
        answer = state.get("answer", "")
        threshold = _effective_groundedness_threshold(state, ctx.groundedness_threshold)

        if not answer or not budget.can_afford_llm_call():
            # Skipped — but we MUST clear pending_retry here. Otherwise a prior
            # verify pass that set it True (now no budget to act on it) would
            # send the router back to generate forever (caught LangGraph at its
            # 10000-step recursion limit during testing).
            #
            # Preserve prior groundedness if a prior verify pass already scored.
            # Without this, a retry that exhausts budget on its second verify
            # would wipe the 0.0 score from the first verify and report
            # low_confidence=False to the user — silent under-warning on the
            # exact failure mode we care most about.
            if not answer:
                score = 1.0
                ungrounded: list[str] = []
            else:
                score = float(state.get("groundedness_score", 0.0))
                ungrounded = list(state.get("ungrounded_claims", []))
            return {
                "groundedness_score": score,
                "ungrounded_claims": ungrounded,
                "low_confidence": bool(answer) and score < threshold,
                "pending_retry": False,
                "trace": _append_trace(state, "verify", budget, "skipped"),
            }

        context_segments = _select_context_segments(state, state.get("top_k", 10))
        # Use full chunk content (not the default 250-char truncation) so the
        # groundedness judge can see ALL evidence.  Without this, claims backed
        # by text past the 250-char mark are wrongly scored as ungrounded.
        chunks_summary = _summarize_chunks_for_judge(context_segments, max_chars=2000)
        user_msg = (
            f"Question: {state['original_query']}\n\n"
            f"Sources:\n{chunks_summary}\n\nAnswer:\n{answer}"
        )

        # Tenacity wraps just the verify LLM call: 3 attempts, exponential 2-10s.
        # The LLM service has its own 3× retry, but it's tuned for general use
        # (1-4s) and silently downgrades rate limits to LLMError. Adding an outer
        # retry buys ~6–18s extra wait specifically for transient 429s before we
        # fall through to the unverified-but-kept-answer path.
        service_error: BaseException | None = None
        score: float | None = None
        ungrounded: list[str] = []
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception(_is_service_error),
                reraise=True,
            ):
                with attempt:
                    result = await ctx.llm.generate_structured(
                        messages=[
                            {"role": "system", "content": VERIFY_SYSTEM},
                            {"role": "user", "content": user_msg},
                        ],
                        response_format=Groundedness,
                        tier="fast",
                        temperature=0.0,
                        max_tokens=512,
                    )
                    # Defence in depth: even with the LLM-service empty-body
                    # guard, a malformed but parseable response (e.g. score as
                    # a string, ungrounded_claims as null) can slip through.
                    # Explicit shape/range check; raise so we land in the
                    # sentinel path instead of surfacing a fake zero.
                    raw_score = result.score
                    if not isinstance(raw_score, (int, float)):
                        raise LLMError(
                            f"Verify returned non-numeric score: {raw_score!r}"
                        )
                    if not (0.0 <= float(raw_score) <= 1.0):
                        raise LLMError(
                            f"Verify returned out-of-range score: {raw_score}"
                        )
                    if not isinstance(result.ungrounded_claims, list):
                        raise LLMError(
                            "Verify returned non-list ungrounded_claims: "
                            f"{type(result.ungrounded_claims).__name__}"
                        )
                    score = float(raw_score)
                    ungrounded = list(result.ungrounded_claims)
                    budget.record_llm_call()
        except RetryError as re:
            service_error = re.last_attempt.exception() or re
        except Exception as e:
            # Either a service error that bypassed retry (e.g. reraise on final
            # attempt) or a genuine non-retryable failure. Treat both as
            # unverified — we never want to silently report score=0 on infra.
            service_error = e

        if service_error is not None:
            err_msg = str(service_error)[:300]
            is_rate_limit = _is_service_error(service_error)
            logger.warning(
                "Verify LLM call failed — keeping answer, marking unverified",
                error=err_msg,
                rate_limit=is_rate_limit,
            )
            # Sentinel: -1.0 means "not verified due to service error", distinct
            # from a genuine 0.0 score. Keep the answer, mark low_confidence so
            # the UI can flag it, surface the error string for audit.
            return {
                "groundedness_score": -1.0,
                "ungrounded_claims": [],
                "low_confidence": True,
                "verification_error": err_msg,
                "pending_retry": False,
                "trace": _append_trace(
                    state,
                    "verify",
                    budget,
                    f"service_error rate_limit={is_rate_limit}",
                ),
            }

        assert score is not None  # Reached the success branch — score is set.

        retries = state.get("generate_retries", 0)
        should_retry = (
            score < threshold
            and retries == 0
            and budget.can_afford_llm_call()
        )

        if should_retry:
            # Bounce back through generate ONCE with stricter prompt.
            return {
                "groundedness_score": score,
                "ungrounded_claims": ungrounded,
                "generate_retries": retries + 1,
                "pending_retry": True,
                "low_confidence": False,
                "trace": _append_trace(
                    state,
                    "verify",
                    budget,
                    f"score={score:.2f} retry_triggered",
                ),
            }

        low_confidence = score < threshold
        return {
            "groundedness_score": score,
            "ungrounded_claims": ungrounded,
            "low_confidence": low_confidence,
            "pending_retry": False,
            "trace": _append_trace(
                state,
                "verify",
                budget,
                f"score={score:.2f} thr={threshold:.2f} low_conf={low_confidence}",
            ),
        }

    return verify


def route_after_retrieve(state: AgenticRAGState) -> str:
    """Decide whether reflect/refine adds value.

    Policy (first pass only — iterations == 0):
      • multi_pass (len(sub_queries) >= 2): plan already decomposed the
        question across concepts. Reflect re-judges sufficiency before generate
        has even tried — pure overhead that historically blew the 15s budget
        before generate could run. Skip straight to generate; let verify do
        the quality check post-hoc.
      • single_pass with >= 3 chunks retrieved: enough material; skip reflect.
      • single_pass with < 3 chunks: genuine retrieval gap — keep reflect/refine
        so it can mark missing topics and drive one refine pass.
      • no chunks at all: keep reflect so it can record the no_segments path
        (graph then proceeds to generate which returns abstention).

    On later passes (iterations > 0): always go through reflect — the refine
    loop already invested an LLM call, let it judge whether to stop.
    """
    sub_queries = state.get("sub_queries", [])
    iterations = state.get("iterations", 0)
    chunk_count = len(state.get("segments_by_id", {}))

    if iterations > 0:
        return "reflect"
    if chunk_count == 0:
        return "reflect"
    if len(sub_queries) >= 2:
        return "generate"
    # single_pass branch
    if chunk_count >= 3:
        return "generate"
    return "reflect"


def route_after_reflect(state: AgenticRAGState) -> str:
    budget = state.get("budget") or AgentBudget()
    if state.get("is_sufficient"):
        return "generate"
    if budget.is_exhausted(state.get("iterations", 0)):
        return "generate"
    return "refine_query"


def route_after_verify(state: AgenticRAGState) -> str:
    return "generate" if state.get("pending_retry") else "end"


def _abstention(language: str) -> str:
    if language == "ar":
        return "هذه المعلومة غير مغطاة في الوثائق المتاحة."
    if language == "en":
        return "This information is not covered by the available documents."
    return "Cette information n'est pas couverte par les documents disponibles."
