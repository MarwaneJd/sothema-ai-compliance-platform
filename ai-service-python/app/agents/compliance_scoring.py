"""Compliance Scoring Agent — generates 0-100 score with 4×25 category breakdown."""

import structlog

from app.agents.state import ComplianceState
from app.api.schemas.analysis import ComplianceScoreOutput
from app.services.llm import LLMService

logger = structlog.get_logger()

SCORING_PROMPT = """You are a pharmaceutical compliance scoring expert.
Based on the regulatory compliance analysis provided, generate a compliance score.

Score the document across exactly 4 categories, each worth 0-25 points:

1. **documentation** (0-25): Completeness of documentation — are all required sections present?
   Are procedures clearly described? Is version control evident?

2. **regulatory** (0-25): Alignment with applicable regulations — does the document reference
   and comply with relevant GMP, ICH, FDA standards? Are regulatory requirements addressed?

3. **quality** (0-25): Quality management practices — are quality controls described?
   Are CAPA processes referenced? Are validation requirements addressed?

4. **traceability** (0-25): Audit readiness and traceability — are records traceable?
   Are responsibilities assigned? Are review/approval workflows documented?

For each category, provide:
- A score (0-25)
- A list of specific findings supporting the score

The total_score must equal the sum of all category scores (0-100).
Be rigorous and evidence-based in your scoring."""


class ComplianceScoringAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def run(self, state: ComplianceState) -> dict:
        """Generate compliance score with category breakdown."""
        logger.info("Compliance scoring agent started", job_id=state.get("job_id"))

        regulatory_findings = state.get("regulatory_findings", [])
        content_analysis = state.get("content_analysis", "")

        # Combine findings into context
        findings_text = ""
        for finding in regulatory_findings:
            if "raw_analysis" in finding:
                findings_text += finding["raw_analysis"] + "\n\n"

        messages = [
            {"role": "system", "content": SCORING_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Content Analysis:\n{content_analysis}\n\n"
                    f"Regulatory Findings:\n{findings_text}"
                ),
            },
        ]

        try:
            score_output: ComplianceScoreOutput = await self.llm.generate_structured(
                messages=messages,
                response_format=ComplianceScoreOutput,
            )

            scores = {
                "categories": {
                    name: {
                        "score": cat.score,
                        "max": cat.max,
                        "findings": cat.findings,
                    }
                    for name, cat in score_output.categories.items()
                },
                "total_score": score_output.total_score,
                "max_score": score_output.max_score,
            }

            logger.info(
                "Compliance scoring complete",
                total_score=score_output.total_score,
                job_id=state.get("job_id"),
            )

            return {
                "scores": scores,
                "current_agent": "compliance_scoring",
            }

        except Exception as e:
            logger.error("Compliance scoring failed", error=str(e))
            return {
                "scores": {
                    "categories": {},
                    "total_score": 0,
                    "max_score": 100,
                    "error": str(e),
                },
                "current_agent": "compliance_scoring",
                "error": f"Compliance scoring failed: {e}",
            }
