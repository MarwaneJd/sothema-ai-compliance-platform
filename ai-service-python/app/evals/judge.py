"""Thin LLM-as-judge for faithfulness and answer-relevance.

Implemented in-house rather than via `ragas` because ragas pulls in
langchain version constraints that conflict with the project's pinned
`langchain-core==0.3.0`. Run on a small subset of the goldset (default
20 queries) to bound LLM cost.

Both scores are floats in [0, 1]:

  - Faithfulness: are all factual claims in `answer` grounded in `sources`?
    1.0 = every claim supported; 0.0 = the answer hallucinates wholesale.

  - Answer relevance: does `answer` actually address `query`, regardless
    of correctness?  1.0 = directly responsive; 0.0 = off-topic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


_FAITHFULNESS_PROMPT = """Tu es un évaluateur strict. Tu reçois une réponse et un ensemble de sources.

Décompose la réponse en affirmations atomiques. Pour chacune, dis si elle est SOUTENUE par les sources fournies (oui/non).

Renvoie UNIQUEMENT un JSON valide de la forme :
{"claims": [{"claim": "...", "supported": true|false}], "score": 0.XX}

où `score` = nombre de claims soutenues / nombre total de claims (0.0 si la réponse ne fait aucune affirmation factuelle).

RÉPONSE :
{answer}

SOURCES :
{sources}
"""

_RELEVANCE_PROMPT = """Tu es un évaluateur strict. Étant donné une question et une réponse, juge si la réponse traite directement la question — INDÉPENDAMMENT de sa correctness factuelle.

Renvoie UNIQUEMENT un JSON valide de la forme :
{"reasoning": "...", "score": 0.XX}

où `score` ∈ [0, 1] : 1.0 = traite directement la question, 0.5 = partiellement, 0.0 = hors sujet.

QUESTION :
{query}

RÉPONSE :
{answer}
"""


@dataclass
class JudgeResult:
    score: float
    raw: dict


async def _judge(prompt: str, llm_service) -> JudgeResult:
    """Single LLM call expecting a JSON object with a `score` field."""
    messages = [
        {"role": "system", "content": "You are a strict evaluator. Output JSON only."},
        {"role": "user", "content": prompt},
    ]
    raw = await llm_service.generate(messages, temperature=0.0, max_tokens=1000)
    try:
        parsed = json.loads(raw)
        score = float(parsed.get("score", 0.0))
        score = max(0.0, min(1.0, score))
        return JudgeResult(score=score, raw=parsed)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Judge returned non-JSON; scoring 0", error=str(e), raw=raw[:200])
        return JudgeResult(score=0.0, raw={"error": str(e), "raw": raw})


async def score_faithfulness(answer: str, sources: list[str], llm_service) -> JudgeResult:
    """How well does `answer` stay grounded in `sources`?"""
    if not answer.strip():
        return JudgeResult(score=0.0, raw={"reason": "empty answer"})
    sources_text = "\n\n---\n\n".join(sources) if sources else "(no sources provided)"
    # str.replace, not .format — the prompt contains literal `{...}` JSON
    # examples that would otherwise be interpreted as format specifiers.
    prompt = _FAITHFULNESS_PROMPT.replace("{answer}", answer).replace("{sources}", sources_text)
    return await _judge(prompt, llm_service)


async def score_answer_relevance(answer: str, query: str, llm_service) -> JudgeResult:
    """Does `answer` actually respond to `query`?"""
    if not answer.strip():
        return JudgeResult(score=0.0, raw={"reason": "empty answer"})
    prompt = _RELEVANCE_PROMPT.replace("{query}", query).replace("{answer}", answer)
    return await _judge(prompt, llm_service)
