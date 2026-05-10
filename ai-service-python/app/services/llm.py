import asyncio
import json
import re
from typing import Literal

import structlog
from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import BaseModel

from app.config import Settings
from app.core.exceptions import LLMError

logger = structlog.get_logger()

MAX_RETRIES = 3
BASE_DELAY = 1.0

Tier = Literal["reasoning", "fast"]


class LLMService:
    """LLM chat completion wrapper supporting Azure OpenAI, Groq, and Ollama providers.

    Two tiers per provider:
      - tier="reasoning" — high-quality model for plan/generate (GPT-5.4 prod, Llama-3.3-70B dev)
      - tier="fast" — cheaper model for verify/reflect/expand (GPT-5.4 mini prod, Llama-3.3-70B dev)

    Call sites pick a tier; provider+model resolution is config-driven.
    """

    def __init__(self, settings: Settings):
        if settings.llm_provider == "groq":
            self.client = AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            self._reasoning_model = settings.groq_model
            self._fast_model = settings.groq_fast_model
            provider = "groq"
        elif settings.llm_provider == "ollama":
            self.client = AsyncOpenAI(
                api_key="ollama",  # Ollama requires a non-empty key; value is ignored
                base_url=settings.ollama_base_url,
                timeout=1800.0,  # 30 min for local CPU inference
            )
            # Ollama in dev only — single model serves both tiers.
            self._reasoning_model = settings.ollama_model
            self._fast_model = settings.ollama_model
            provider = "ollama"
        else:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self._reasoning_model = settings.azure_openai_chat_deployment
            self._fast_model = settings.azure_openai_chat_deployment_fast
            provider = "azure"

        logger.info(
            "LLM provider initialized",
            provider=provider,
            reasoning_model=self._reasoning_model,
            fast_model=self._fast_model,
        )

    @property
    def model(self) -> str:
        """Backwards-compatible alias for the reasoning-tier model."""
        return self._reasoning_model

    def _resolve_model(self, tier: Tier) -> str:
        return self._fast_model if tier == "fast" else self._reasoning_model

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        *,
        tier: Tier = "reasoning",
    ) -> str:
        """Generate a chat completion. Returns the response content string."""
        model = self._resolve_model(tier)
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or ""
                # Strip qwen3's <think>...</think> blocks if present
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

                logger.info(
                    "LLM response generated",
                    tier=tier,
                    model=model,
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
                        tier=tier,
                        model=model,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)

        raise LLMError(f"LLM request failed after {MAX_RETRIES} retries: {last_error}")

    async def generate_structured(
        self,
        messages: list[dict],
        response_format: type[BaseModel],
        temperature: float = 0.1,
        max_tokens: int = 8192,
        *,
        tier: Tier = "reasoning",
    ) -> BaseModel:
        """Generate a structured response using JSON mode. Parses into the given Pydantic model."""
        model = self._resolve_model(tier)
        last_error: Exception | None = None

        # Add JSON instruction to system message
        # /no_think disables qwen3's thinking mode to avoid wasting tokens
        json_instruction = (
            f"\n/no_think\nYou must respond with ONLY valid JSON matching this schema (no explanation, no markdown):\n"
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
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=enhanced_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or "{}"
                # Strip qwen3's <think>...</think> blocks if present
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

                logger.info(
                    "Structured LLM response generated",
                    tier=tier,
                    model=model,
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
                        tier=tier,
                        model=model,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)

        raise LLMError(
            f"Structured LLM request failed after {MAX_RETRIES} retries: {last_error}"
        )
