"""Audit Agent — records execution trace to AuditLog table. Terminal node."""

import json
import uuid
from datetime import datetime

import structlog

from app.agents.state import ComplianceState
from app.db.models import AuditLog
from app.db.repositories import AuditLogRepository
from app.db.session import async_session_factory

logger = structlog.get_logger()


class AuditAgent:
    def __init__(self, audit_repo: AuditLogRepository):
        # audit_repo kept for interface compatibility but we open a fresh session
        # to avoid poisoning the shared analysis session on failure
        self.audit_repo = audit_repo

    async def run(self, state: ComplianceState) -> dict:
        """Record the full agent execution trace to the audit log."""
        logger.info("Audit agent started", job_id=state.get("job_id"))

        job_id = state.get("job_id", "")
        status = state.get("status", "completed")
        error = state.get("error")

        # Keep audit details lightweight — full scores are stored in ComplianceAnalysis.Details
        # FreeTDS truncates large string parameters even on NVARCHAR(MAX) columns
        scores = state.get("scores") or {}
        categories = scores.get("categories", {})
        details = {
            "document_title": state.get("document_title", "")[:200],
            "segments_retrieved": len(state.get("retrieved_segments", [])),
            "has_content_analysis": bool(state.get("content_analysis")),
            "has_regulatory_findings": bool(state.get("regulatory_findings")),
            "total_score": scores.get("total_score"),
            "max_score": scores.get("max_score"),
            "category_scores": {
                name: cat.get("score") for name, cat in categories.items()
            },
            "status": status,
        }
        if error:
            details["error"] = str(error)[:500]

        audit_entries = []

        try:
            log = AuditLog(
                Id=uuid.uuid4(),
                UserId="ai-service",
                Action="ComplianceAnalysis",
                EntityType="ComplianceAnalysis",
                EntityId=job_id,
                Timestamp=datetime.utcnow(),
                Details=json.dumps(details),
            )

            # Use a fresh isolated session so audit failure never taints
            # the parent session that saves the compliance analysis results
            async with async_session_factory() as session:
                repo = AuditLogRepository(session)
                await repo.create(log)
                await session.commit()

            audit_entries.append(
                {
                    "id": str(log.Id),
                    "action": log.Action,
                    "entity_type": log.EntityType,
                    "entity_id": log.EntityId,
                    "timestamp": log.Timestamp.isoformat(),
                }
            )

            logger.info("Audit log created", job_id=job_id)

        except Exception as e:
            logger.error("Audit logging failed", error=str(e), job_id=job_id)
            audit_entries.append({"error": str(e)})

        return {
            "audit_entries": audit_entries,
            "current_agent": "audit",
        }
