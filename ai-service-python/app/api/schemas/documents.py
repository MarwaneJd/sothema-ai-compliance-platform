from uuid import UUID

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    document_id: UUID = Field(description="Document.Id already created by .NET backend")
    content: str = Field(description="Base64-encoded file content")
    file_type: str = Field(description="File extension: pdf, docx, xlsx, pptx, txt")
    title: str = Field(description="Document title")


class DocumentIngestResponse(BaseModel):
    document_id: UUID
    segments_created: int
    vectors_indexed: int
    status: str  # "success" or "error"
    message: str | None = None


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    title: str | None
    segment_count: int
    indexed: bool


class TextSegmentResponse(BaseModel):
    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    vector_store_id: str | None
