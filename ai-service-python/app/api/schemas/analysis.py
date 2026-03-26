from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    document_id: UUID
    document_content: str = Field(description="Base64-encoded file content")
    file_type: str
    title: str


class AnalysisResponse(BaseModel):
    job_id: UUID
    status: str  # "pending"
    message: str


class AnalysisStatusResponse(BaseModel):
    job_id: UUID
    status: str  # "pending" | "processing" | "completed" | "failed"
    score: float | None = None
    summary: str | None = None
    details: dict | None = None
    analyzed_at: datetime | None = None


# Structured output for compliance scoring agent
class CategoryScore(BaseModel):
    score: int = Field(ge=0, le=25)
    max: int = 25
    findings: list[str]


class ComplianceScoreOutput(BaseModel):
    categories: dict[str, CategoryScore]
    total_score: int = Field(ge=0, le=100)
    max_score: int = 100
