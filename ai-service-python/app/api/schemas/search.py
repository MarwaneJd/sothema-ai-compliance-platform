from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    include_answer: bool = Field(
        default=True,
        description="If False, skip the LLM step and return ranked chunks only.",
    )


class SearchResult(BaseModel):
    document_id: UUID
    document_title: str
    segment_content: str
    chunk_index: int
    relevance_score: float
    vector_store_id: str


class SearchResponse(BaseModel):
    query: str
    answer: str
    results: list[SearchResult]
    total_results: int
