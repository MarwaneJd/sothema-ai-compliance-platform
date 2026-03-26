"""Audit Agent — records execution trace to AuditLog table. Terminal node."""

import json
import uuid
from datetime import datetime

import structlog

from app.agents.state import ComplianceState
from app.db.models import AuditLog
from app.db.repositories import AuditLogRepository

logger = structlog.get_logger()


class AuditAgent:
    def __init__(self, audit_repo: AuditLogRepository):
        self.audit_repo = audit_repo

    async def run(self, state: ComplianceState) -> dict:
        """Record the full agent execution trace to the audit log."""
        logger.info("Audit agent started", job_id=state.get("job_id"))

        job_id = state.get("job_id", "")
        document_id = state.get("document_id", "")
        status = state.get("status", "completed")
        error = state.get("error")

        # Build audit trail details
        details = {
            "document_title": state.get("document_title", ""),
            "segments_retrieved": len(state.get("retrieved_segments", [])),
            "has_content_analysis": bool(state.get("content_analysis")),
            "has_regulatory_findings": bool(state.get("regulatory_findings")),
            "scores": state.get("scores"),
            "status": status,
        }
        if error:
            details["error"] = error

        audit_entries = []

        try:
            # Create audit log entry for the analysis
            log = AuditLog(
                Id=uuid.uuid4(),
                UserId="ai-service",  # System action
                Action="ComplianceAnalysis",
                EntityType="ComplianceAnalysis",
                EntityId=job_id,
                Timestamp=datetime.utcnow(),
                Details=json.dumps(details),
            )
            await self.audit_repo.create(log)

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
