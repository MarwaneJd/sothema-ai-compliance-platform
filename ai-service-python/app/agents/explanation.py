"""Explanation Agent — generates human-readable compliance assessment summary."""

import structlog

from app.agents.state import ComplianceState
from app.services.llm import LLMService

logger = structlog.get_logger()

EXPLANATION_PROMPT = """You are a pharmaceutical compliance communication expert.
Generate a clear, professional compliance assessment summary for stakeholders.

The summary should include:
1. **Overall Assessment**: A brief overall compliance status statement
2. **Score Breakdown**: Explain what each category score means in plain language
3. **Key Strengths**: What the document does well from a compliance perspective
4. **Areas for Improvement**: Critical gaps and recommended actions, prioritized by risk
5. **Regulatory References**: Which specific standards or guidelines are relevant

Write in a professional but accessible tone. Reference specific document sections
and regulatory standards where applicable.
Keep the summary concise (300-500 words)."""


class ExplanationAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def run(self, state: ComplianceState) -> dict:
        """Generate human-readable explanation of the compliance assessment."""
        logger.info("Explanation agent started", job_id=state.get("job_id"))

        scores = state.get("scores", {})
        regulatory_findings = state.get("regulatory_findings", [])
        content_analysis = state.get("content_analysis", "")
        document_title = state.get("document_title", "")

        # Build context for explanation
        findings_text = ""
        for finding in regulatory_findings:
            if "raw_analysis" in finding:
                findings_text += finding["raw_analysis"] + "\n\n"

        scores_text = f"Total Score: {scores.get('total_score', 0)}/100\n"
        for cat_name, cat_data in scores.get("categories", {}).items():
            scores_text += f"  {cat_name}: {cat_data.get('score', 0)}/{cat_data.get('max', 25)}\n"

        messages = [
            {"role": "system", "content": EXPLANATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Document: {document_title}\n\n"
                    f"Compliance Scores:\n{scores_text}\n\n"
                    f"Content Analysis:\n{content_analysis}\n\n"
                    f"Regulatory Findings:\n{findings_text}"
                ),
            },
        ]

        try:
            explanation = await self.llm.generate(messages)

            logger.info("Explanation generated", job_id=state.get("job_id"))

            return {
                "explanation": explanation,
                "current_agent": "explanation",
            }

        except Exception as e:
            logger.error("Explanation generation failed", error=str(e))
            return {
                "explanation": f"Explanation generation failed: {e}",
                "current_agent": "explanation",
                "error": f"Explanation generation failed: {e}",
            }
