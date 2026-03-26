"""LangGraph graph construction for the compliance analysis pipeline.

Flow: Supervisor → Document Retrieval → Content Analysis → Regulatory Compliance
     → Compliance Scoring → Explanation → Audit → END
"""

import structlog
from langgraph.graph import END, StateGraph

from app.agents.audit import AuditAgent
from app.agents.compliance_scoring import ComplianceScoringAgent
from app.agents.content_analysis import ContentAnalysisAgent
from app.agents.document_retrieval import DocumentRetrievalAgent
from app.agents.explanation import ExplanationAgent
from app.agents.regulatory_compliance import RegulatoryComplianceAgent
from app.agents.state import ComplianceState
from app.agents.supervisor import route_next_agent

logger = structlog.get_logger()


def build_compliance_graph(
    doc_retrieval: DocumentRetrievalAgent,
    content_analysis: ContentAnalysisAgent,
    regulatory: RegulatoryComplianceAgent,
    scoring: ComplianceScoringAgent,
    explanation: ExplanationAgent,
    audit: AuditAgent,
) -> StateGraph:
    """Build and compile the LangGraph compliance analysis pipeline."""
    graph = StateGraph(ComplianceState)

    # Add agent nodes
    graph.add_node("document_retrieval", doc_retrieval.run)
    graph.add_node("content_analysis", content_analysis.run)
    graph.add_node("regulatory_compliance", regulatory.run)
    graph.add_node("compliance_scoring", scoring.run)
    graph.add_node("explanation", explanation.run)
    graph.add_node("audit", audit.run)

    # Entry point: supervisor routes to the first agent
    graph.set_conditional_entry_point(
        route_next_agent,
        {
            "document_retrieval": "document_retrieval",
            "content_analysis": "content_analysis",
            "regulatory_compliance": "regulatory_compliance",
            "compliance_scoring": "compliance_scoring",
            "explanation": "explanation",
            "audit": "audit",
            "end": END,
        },
    )

    # After each agent, supervisor routes to the next
    for node in [
        "document_retrieval",
        "content_analysis",
        "regulatory_compliance",
        "compliance_scoring",
        "explanation",
    ]:
        graph.add_conditional_edges(
            node,
            route_next_agent,
            {
                "document_retrieval": "document_retrieval",
                "content_analysis": "content_analysis",
                "regulatory_compliance": "regulatory_compliance",
                "compliance_scoring": "compliance_scoring",
                "explanation": "explanation",
                "audit": "audit",
                "end": END,
            },
        )

    # Audit is the terminal node — always goes to END
    graph.add_edge("audit", END)

    return graph.compile()


async def run_compliance_pipeline(
    job_id: str,
    document_id: str,
    document_content: str,
    document_title: str,
    doc_retrieval: DocumentRetrievalAgent,
    content_analysis: ContentAnalysisAgent,
    regulatory: RegulatoryComplianceAgent,
    scoring: ComplianceScoringAgent,
    explanation: ExplanationAgent,
    audit: AuditAgent,
) -> ComplianceState:
    """Run the full compliance analysis pipeline and return the final state."""
    logger.info("Starting compliance pipeline", job_id=job_id, document_id=document_id)

    compiled_graph = build_compliance_graph(
        doc_retrieval=doc_retrieval,
        content_analysis=content_analysis,
        regulatory=regulatory,
        scoring=scoring,
        explanation=explanation,
        audit=audit,
    )

    initial_state: ComplianceState = {
        "job_id": job_id,
        "document_id": document_id,
        "document_content": document_content,
        "document_title": document_title,
        "retrieved_segments": [],
        "content_analysis": "",
        "regulatory_findings": [],
        "scores": {},
        "explanation": "",
        "audit_entries": [],
        "current_agent": "",
        "status": "processing",
        "error": "",
    }

    final_state = await compiled_graph.ainvoke(initial_state)

    logger.info(
        "Compliance pipeline complete",
        job_id=job_id,
        status=final_state.get("status", "unknown"),
        total_score=final_state.get("scores", {}).get("total_score"),
    )

    return final_state
