import pytest

from app.agents.supervisor import route_next_agent
from app.agents.state import ComplianceState


class TestSupervisorRouting:
    def test_routes_to_document_retrieval_first(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
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
        assert route_next_agent(state) == "document_retrieval"

    def test_routes_to_content_analysis_after_retrieval(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [{"id": "seg-1"}],
            "content_analysis": "",
            "regulatory_findings": [],
            "scores": {},
            "explanation": "",
            "audit_entries": [],
            "current_agent": "document_retrieval",
            "status": "processing",
            "error": "",
        }
        assert route_next_agent(state) == "content_analysis"

    def test_routes_to_regulatory_after_content(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [{"id": "seg-1"}],
            "content_analysis": "analysis done",
            "regulatory_findings": [],
            "scores": {},
            "explanation": "",
            "audit_entries": [],
            "current_agent": "content_analysis",
            "status": "processing",
            "error": "",
        }
        assert route_next_agent(state) == "regulatory_compliance"

    def test_routes_to_scoring_after_regulatory(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [{"id": "seg-1"}],
            "content_analysis": "analysis done",
            "regulatory_findings": [{"finding": "gap"}],
            "scores": {},
            "explanation": "",
            "audit_entries": [],
            "current_agent": "regulatory_compliance",
            "status": "processing",
            "error": "",
        }
        assert route_next_agent(state) == "compliance_scoring"

    def test_routes_to_explanation_after_scoring(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [{"id": "seg-1"}],
            "content_analysis": "analysis done",
            "regulatory_findings": [{"finding": "gap"}],
            "scores": {"total_score": 75},
            "explanation": "",
            "audit_entries": [],
            "current_agent": "compliance_scoring",
            "status": "processing",
            "error": "",
        }
        assert route_next_agent(state) == "explanation"

    def test_routes_to_audit_after_explanation(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [{"id": "seg-1"}],
            "content_analysis": "analysis done",
            "regulatory_findings": [{"finding": "gap"}],
            "scores": {"total_score": 75},
            "explanation": "The document scores 75/100.",
            "audit_entries": [],
            "current_agent": "explanation",
            "status": "processing",
            "error": "",
        }
        assert route_next_agent(state) == "audit"

    def test_routes_to_end_after_audit(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [{"id": "seg-1"}],
            "content_analysis": "analysis done",
            "regulatory_findings": [{"finding": "gap"}],
            "scores": {"total_score": 75},
            "explanation": "The document scores 75/100.",
            "audit_entries": [{"id": "audit-1"}],
            "current_agent": "audit",
            "status": "completed",
            "error": "",
        }
        assert route_next_agent(state) == "end"

    def test_routes_to_audit_on_error(self):
        state: ComplianceState = {
            "job_id": "test",
            "document_id": "doc-1",
            "document_content": "content",
            "document_title": "title",
            "retrieved_segments": [],
            "content_analysis": "",
            "regulatory_findings": [],
            "scores": {},
            "explanation": "",
            "audit_entries": [],
            "current_agent": "",
            "status": "failed",
            "error": "Something went wrong",
        }
        assert route_next_agent(state) == "audit"
