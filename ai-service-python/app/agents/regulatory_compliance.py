"""Regulatory Compliance Agent — checks content against pharmaceutical regulatory requirements."""

import structlog

from app.agents.state import ComplianceState
from app.services.llm import LLMService

logger = structlog.get_logger()

REGULATORY_PROMPT = """You are a pharmaceutical regulatory compliance expert.
Based on the content analysis provided, evaluate the document against applicable regulatory requirements.

Consider the following frameworks and standards:
- **GMP (Good Manufacturing Practice)** — EU GMP Annex guidelines
- **ICH Q7** — Good Manufacturing Practice for Active Pharmaceutical Ingredients
- **ICH Q10** — Pharmaceutical Quality System
- **FDA 21 CFR Part 211** — Current Good Manufacturing Practice for Finished Pharmaceuticals
- **FDA 21 CFR Part 11** — Electronic Records; Electronic Signatures
- **ISO 9001** — Quality Management Systems
- **WHO GMP Guidelines** — for pharmaceutical products

For each applicable standard, identify:
1. **Requirements Met**: Which regulatory requirements are adequately addressed
2. **Compliance Gaps**: Which requirements are missing or insufficiently addressed
3. **Risk Areas**: Potential compliance risks identified
4. **Regulatory References**: Specific sections/clauses of applicable standards

Provide your findings as a structured list of compliance findings.
Each finding should include: category, finding, applicable_standard, risk_level (high/medium/low), and recommendation."""


class RegulatoryComplianceAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def run(self, state: ComplianceState) -> dict:
        """Evaluate document against regulatory requirements."""
        logger.info("Regulatory compliance agent started", job_id=state.get("job_id"))

        content_analysis = state.get("content_analysis", "")

        messages = [
            {"role": "system", "content": REGULATORY_PROMPT},
            {
                "role": "user",
                "content": f"Content Analysis:\n\n{content_analysis}",
            },
        ]

        try:
            response = await self.llm.generate(messages)

            # Parse findings into structured format
            findings = [
                {
                    "raw_analysis": response,
                    "agent": "regulatory_compliance",
                }
            ]

            logger.info("Regulatory compliance analysis complete", job_id=state.get("job_id"))

            return {
                "regulatory_findings": findings,
                "current_agent": "regulatory_compliance",
            }

        except Exception as e:
            logger.error("Regulatory compliance analysis failed", error=str(e))
            return {
                "regulatory_findings": [{"error": str(e)}],
                "current_agent": "regulatory_compliance",
                "error": f"Regulatory compliance analysis failed: {e}",
            }
