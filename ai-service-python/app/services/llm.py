import json
import time

import structlog
from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel

from app.config import Settings
from app.core.exceptions import LLMError

logger = structlog.get_logger()

MAX_RETRIES = 3
BASE_DELAY = 1.0


class LLMService:
    """LLM chat completion wrapper supporting Azure OpenAI and Groq providers."""

    def __init__(self, settings: Settings):
        if settings.llm_provider == "groq":
            self.client = OpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            self.model = settings.groq_model
            logger.info("LLM provider initialized", provider="groq", model=self.model)
        else:
            self.client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.azure_openai_chat_deployment
            logger.info("LLM provider initialized", provider="azure", model=self.model)

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a chat completion. Returns the response content string."""
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or ""

                logger.info(
                    "LLM response generated",
                    model=self.model,
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                )
                return content

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2**attempt)
                    logger.warning(
                        "LLM request failed, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)

        raise LLMError(f"LLM request failed after {MAX_RETRIES} retries: {last_error}")

    async def generate_structured(
        self,
        messages: list[dict],
        response_format: type[BaseModel],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Generate a structured response using JSON mode. Parses into the given Pydantic model."""
        last_error: Exception | None = None

        # Add JSON instruction to system message
        json_instruction = (
            f"\nYou must respond with valid JSON matching this schema:\n"
            f"{json.dumps(response_format.model_json_schema(), indent=2)}"
        )
        enhanced_messages = list(messages)
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            enhanced_messages[0] = {
                **enhanced_messages[0],
                "content": enhanced_messages[0]["content"] + json_instruction,
            }
        else:
            enhanced_messages.insert(0, {"role": "system", "content": json_instruction})

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=enhanced_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or "{}"

                logger.info(
                    "Structured LLM response generated",
                    model=self.model,
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                )

                return response_format.model_validate_json(content)

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Structured LLM request failed, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)

        raise LLMError(
            f"Structured LLM request failed after {MAX_RETRIES} retries: {last_error}"
        )
