"""Agent state and supporting types."""

from dataclasses import dataclass
from typing import TypedDict

from app.agents.agentic_rag.budget import AgentBudget
from app.db.models import TextSegment
from app.rag.hybrid_retriever import RetrievedSegment


@dataclass
class Citation:
    """A single citation in the final answer."""

    source_index: int  # The [Source N] number — corresponds to ChunkIndex
    document_id: str
    document_title: str
    chunk_index: int
    vector_store_id: str


@dataclass
class StepLog:
    """One row of the agent's execution trace — surfaced in the API response for audit."""

    step: str  # "plan" / "retrieve" / "reflect" / "refine_query" / "generate" / "verify"
    iteration: int
    elapsed_ms: int
    detail: str = ""


class AgenticRAGState(TypedDict, total=False):
    """LangGraph state. `total=False` so partial dicts from nodes merge cleanly.

    Conventions:
    - Lists are appended to / merged by node returns (LangGraph reducer pattern).
    - Counters (iterations) are written as absolute values, not deltas.
    """

    # Input
    original_query: str
    language: str  # "fr" / "en" / "ar" — detected in `plan`
    top_k: int

    # Planning / refinement
    sub_queries: list[str]  # appended across iterations; dedup'd in retrieve

    # Retrieval accumulation. Keyed by vector_store_id for dedup.
    retrieved: list[RetrievedSegment]
    segments_by_id: dict[str, TextSegment]

    # Loop control
    iterations: int
    budget: AgentBudget
    is_sufficient: bool  # set by `reflect`, read by router
    missing: list[str]  # set by `reflect`, fed to `refine_query`

    # Generation output
    answer: str
    citations: list[Citation]

    # Verification
    groundedness_score: float  # -1.0 sentinel = "not verified" (service error); 0.0–1.0 = real score
    ungrounded_claims: list[str]
    low_confidence: bool
    verification_error: str | None  # populated when verify failed due to a service/rate-limit error
    generate_retries: int  # 0 or 1 — used by `verify` to decide whether to retry
    pending_retry: bool  # set True by `verify` to route back to `generate`; cleared on retry entry

    # Internal — sub-queries we've already issued to retrieve. Lets refine_query
    # iterations skip re-running prior sub-queries.
    executed_sub_queries: list[str]

    # Audit
    trace: list[StepLog]
