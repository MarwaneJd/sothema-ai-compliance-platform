"""Content Analysis Agent — extracts structured information from document content."""

import structlog

from app.agents.state import ComplianceState
from app.services.llm import LLMService

logger = structlog.get_logger()

CONTENT_ANALYSIS_PROMPT = """You are a pharmaceutical document content analyst.
Analyze the following document and provide a structured summary covering:

1. **Document Type**: What kind of document is this? (SOP, policy, guideline, report, etc.)
2. **Key Topics**: Main subjects and sections covered
3. **Regulatory References**: Any standards, guidelines, or regulations mentioned (GMP, ICH, FDA, EMA, etc.)
4. **Process Descriptions**: Key processes or procedures described
5. **Critical Requirements**: Important requirements, specifications, or criteria stated
6. **Defined Responsibilities**: Roles and responsibilities mentioned

Provide a clear, structured analysis that can be used for compliance assessment."""


class ContentAnalysisAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def run(self, state: ComplianceState) -> dict:
        """Analyze document content and extract structured information."""
        logger.info("Content analysis agent started", job_id=state.get("job_id"))

        document_content = state.get("document_content", "")
        document_title = state.get("document_title", "")

        # Truncate content if too long (keep within LLM context limits)
        max_content_chars = 30000
        content = document_content[:max_content_chars]

        messages = [
            {"role": "system", "content": CONTENT_ANALYSIS_PROMPT},
            {
                "role": "user",
                "content": f"Document Title: {document_title}\n\nDocument Content:\n{content}",
            },
        ]

        try:
            analysis = await self.llm.generate(messages)

            logger.info("Content analysis complete", job_id=state.get("job_id"))

            return {
                "content_analysis": analysis,
                "current_agent": "content_analysis",
            }

        except Exception as e:
            logger.error("Content analysis failed", error=str(e))
            return {
                "content_analysis": f"Content analysis failed: {e}",
                "current_agent": "content_analysis",
                "error": f"Content analysis failed: {e}",
            }
