from typing import TypedDict


class ComplianceState(TypedDict, total=False):
    """Shared state passed through the LangGraph compliance analysis pipeline."""

    # Input
    job_id: str  # ComplianceAnalysis.Id
    document_id: str
    document_content: str  # Extracted plain text
    document_title: str

    # Agent outputs (accumulated through the pipeline)
    retrieved_segments: list[dict]  # From document retrieval agent
    content_analysis: str  # From content analysis agent
    regulatory_findings: list[dict]  # From regulatory compliance agent
    scores: dict  # From compliance scoring agent (4×25 breakdown)
    explanation: str  # From explanation agent (maps to ComplianceAnalysis.Summary)
    audit_entries: list[dict]  # From audit agent

    # Control
    current_agent: str
    status: str  # "pending" | "processing" | "completed" | "failed"
    error: str
