"""Multi-query expansion via LLM (Phase 2).

Generates N rewritten variants of the user's query so the multi-query retriever
can fuse retrievals across phrasings. Better than HyDE for regulatory text —
HyDE fabricates terminology, expansion only rephrases.

Uses the `tier="fast"` LLM and a per-process LRU cache. On timeout the caller
gets back an empty list and falls back to the original query alone — degrading
gracefully rather than blocking the Fast-mode SLA.
"""

from __future__ import annotations

import asyncio
import unicodedata
from collections import OrderedDict

import structlog
from pydantic import BaseModel, Field

from app.services.llm import LLMService

logger = structlog.get_logger()


class ExpandedQueries(BaseModel):
    queries: list[str] = Field(
        default_factory=list,
        description="Rewritten query variants targeting the same information need.",
    )


SYSTEM_PROMPT_FR_EN = """You rewrite a user's pharmaceutical compliance question into {n} alternative phrasings.
Each rewrite must:
- Preserve the original intent and any specific regulation names (BPF, GMP, Annex 16, ICH Q7, etc.).
- Use different vocabulary or sentence structure than the original (synonyms, restated focus, alternate French/English/scientific phrasing where appropriate).
- Stay one sentence and ≤ 25 words.
- NOT invent specific clauses, section numbers, or terminology not implied by the original.

Return JSON: {{"queries": ["...", "...", "..."]}}. Exactly {n} items."""

SYSTEM_PROMPT_AR = """تُعيد صياغة سؤال المستخدم حول الامتثال الصيدلاني إلى {n} صيغ بديلة.
كل إعادة صياغة يجب أن:
- تحافظ على القصد الأصلي وأي أسماء لوائح محددة (BPF, GMP, Annex 16, ICH Q7, إلخ).
- تستخدم مفردات أو بنية جملة مختلفة عن الأصل.
- تبقى جملة واحدة و ≤ 25 كلمة.
- لا تخترع بنوداً أو أرقام أقسام أو مصطلحات غير ضمنية في الأصل.

أعد JSON: {{"queries": ["...", "...", "..."]}}. بالضبط {n} عناصر."""


def _is_arabic(text: str) -> bool:
    """Detect dominant script. Arabic Unicode block: U+0600–U+06FF."""
    arabic_count = sum(1 for ch in text if "؀" <= ch <= "ۿ")
    letters = sum(1 for ch in text if unicodedata.category(ch).startswith("L"))
    return letters > 0 and (arabic_count / letters) > 0.3


class _LRUCache:
    """Tiny capacity-bounded ordered cache. Keyed by query string."""

    def __init__(self, capacity: int):
        self._capacity = capacity
        self._data: OrderedDict[str, list[str]] = OrderedDict()

    def get(self, key: str) -> list[str] | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: str, value: list[str]) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)


class QueryExpander:
    """LLM-driven multi-query rewriter with cache + hard timeout."""

    def __init__(
        self,
        llm_service: LLMService,
        n: int = 3,
        timeout_ms: int = 800,
        cache_size: int = 2048,
    ):
        self._llm = llm_service
        self._n = n
        self._timeout_s = timeout_ms / 1000.0
        self._cache = _LRUCache(capacity=cache_size)

    async def expand(self, query: str, n: int | None = None) -> list[str]:
        """Return up to `n` rewrites. On timeout/error/parse failure, return [].

        Caller is expected to combine the rewrites with the original query
        before retrieval — this method intentionally does NOT include the
        original in the returned list.
        """
        target = n or self._n
        cached = self._cache.get(query)
        if cached is not None:
            return cached[:target]

        try:
            rewrites = await asyncio.wait_for(
                self._call_llm(query, target), timeout=self._timeout_s
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Query expansion timed out, falling back to original",
                query_preview=query[:80],
                timeout_s=self._timeout_s,
            )
            return []
        except Exception as e:
            logger.warning(
                "Query expansion failed, falling back to original",
                query_preview=query[:80],
                error=str(e)[:200],
            )
            return []

        self._cache.put(query, rewrites)
        return rewrites[:target]

    async def _call_llm(self, query: str, target: int) -> list[str]:
        prompt_template = SYSTEM_PROMPT_AR if _is_arabic(query) else SYSTEM_PROMPT_FR_EN
        system_prompt = prompt_template.format(n=target)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        result = await self._llm.generate_structured(
            messages=messages,
            response_format=ExpandedQueries,
            temperature=0.3,
            max_tokens=512,
            tier="fast",
        )
        # Defensive: dedupe, strip whitespace, drop empties + the original query.
        seen: set[str] = {query.strip().lower()}
        clean: list[str] = []
        for q in result.queries:  # type: ignore[attr-defined]
            qn = q.strip()
            key = qn.lower()
            if not qn or key in seen:
                continue
            seen.add(key)
            clean.append(qn)
        logger.info(
            "Query expanded",
            query_preview=query[:80],
            requested=target,
            returned=len(clean),
        )
        return clean
