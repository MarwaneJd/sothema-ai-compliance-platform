"""Pydantic schemas for the Deep Analysis (agentic RAG) endpoint."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.search import SearchResult


class AgenticSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    max_iterations: int = Field(default=2, ge=1, le=4)


class CitationDTO(BaseModel):
    source_index: int
    document_id: UUID
    document_title: str
    chunk_index: int
    vector_store_id: str


class StepLogDTO(BaseModel):
    step: str
    iteration: int
    elapsed_ms: int
    detail: str = ""


class AgenticSearchResponse(BaseModel):
    query: str
    answer: str
    results: list[SearchResult]
    total_results: int
    # Agent-specific:
    citations: list[CitationDTO]
    groundedness_score: float  # -1.0 = not verified (service error); 0.0–1.0 = real score
    low_confidence: bool
    verification_error: str | None = None  # set when verify failed (rate limit, timeout, etc.)
    iterations: int
    sub_queries: list[str]
    trace: list[StepLogDTO]
    llm_calls: int
    elapsed_ms: int
