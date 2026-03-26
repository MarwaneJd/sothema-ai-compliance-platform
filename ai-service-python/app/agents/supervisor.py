"""Supervisor/router agent — deterministic routing through the compliance pipeline.

No LLM needed: the pipeline is sequential and the supervisor inspects state
to determine which agent should run next.
"""

from app.agents.state import ComplianceState


def route_next_agent(state: ComplianceState) -> str:
    """Determine the next agent to invoke based on which state fields are populated."""
    if state.get("error"):
        return "audit"

    if not state.get("retrieved_segments"):
        return "document_retrieval"

    if not state.get("content_analysis"):
        return "content_analysis"

    if not state.get("regulatory_findings"):
        return "regulatory_compliance"

    if not state.get("scores"):
        return "compliance_scoring"

    if not state.get("explanation"):
        return "explanation"

    if not state.get("audit_entries"):
        return "audit"

    return "end"
