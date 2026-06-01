"""Prompts for the agent nodes.

Three system languages — FR / EN / AR — picked by script detection at plan time.
All structured-output prompts request JSON; the calling code uses Pydantic to
validate, with graceful fallbacks on parse failure.
"""

from __future__ import annotations

import re
import unicodedata

# French diacritics — their presence is a strong French signal that won't trip
# on English text (which uses none) but also won't false-trigger on English
# loanwords like "café" (rare in compliance questions; if it happens, word-level
# stopword counts disambiguate).
_FR_DIACRITICS = set("àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ")

# Frequent function words. Disjoint sets — these never collide between FR / EN
# in compliance-question contexts.
_FR_STOPWORDS = {
    "le", "la", "les", "de", "du", "des", "et", "est", "sont", "que", "qui",
    "quel", "quelle", "quels", "quelles", "pour", "dans", "avec", "sur", "par",
    "ce", "ces", "il", "elle", "ils", "elles", "un", "une", "ou", "ne", "pas",
    "selon", "comment", "où", "ou", "aux", "au", "se", "lors", "lorsque",
}
_EN_STOPWORDS = {
    "the", "is", "are", "and", "of", "to", "in", "for", "what", "how", "with",
    "this", "that", "from", "by", "an", "a", "as", "be", "do", "does",
    "according", "where", "when", "which", "who", "between", "must", "should",
}

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def detect_language(text: str) -> str:
    """Return 'fr' / 'en' / 'ar' for compliance-question text.

    Priority:
    1. Arabic Unicode block dominance → "ar"
    2. Any French diacritic → "fr"
    3. Stopword vote between FR / EN
    4. Tie or no signal → "fr" (primary user language for this product)
    """
    if not text:
        return "fr"

    letters = [ch for ch in text if unicodedata.category(ch).startswith("L")]
    if letters and sum(1 for ch in letters if "؀" <= ch <= "ۿ") / len(letters) > 0.3:
        return "ar"

    if any(ch in _FR_DIACRITICS for ch in text):
        return "fr"

    words = {m.group(0).lower() for m in _WORD_RE.finditer(text)}
    fr_hits = len(words & _FR_STOPWORDS)
    en_hits = len(words & _EN_STOPWORDS)
    if fr_hits > en_hits:
        return "fr"
    if en_hits > fr_hits:
        return "en"
    return "fr"


# ─── plan ─────────────────────────────────────────────────────────────────────

PLAN_SYSTEM_FR = """Tu analyses une question de conformité pharmaceutique et choisis une stratégie de récupération.

Règles:
- Si la question demande UN seul fait précis: retourne UNE sous-requête (la question telle quelle, ou légèrement reformulée).
- Si la question est multi-aspects (comparaison, plusieurs sections, plusieurs réglementations): décompose en 2 ou 3 sous-questions indépendantes, chacune récupérable seule.
- Maximum 3 sous-requêtes. Chacune doit être en français, ≤ 25 mots, ne pas inventer de termes techniques absents de la question.
- N'utilise pas la décomposition par reformulation (synonymes) — c'est le rôle d'un autre composant. Décompose par CONCEPT.

Réponds en JSON strict: {"sub_queries": ["...", "..."]}."""

PLAN_SYSTEM_EN = """You analyze a pharmaceutical compliance question and choose a retrieval strategy.

Rules:
- If the question asks ONE specific fact: return ONE sub-query (the question as-is, or lightly rephrased).
- If the question is multi-aspect (comparison, multiple sections, multiple regulations): decompose into 2 or 3 independent sub-questions, each retrievable on its own.
- Maximum 3 sub-queries. Each must be in English, ≤ 25 words, and must not invent technical terms absent from the question.
- Do NOT decompose by paraphrase (synonyms) — that's another component's job. Decompose by CONCEPT.

Respond in strict JSON: {"sub_queries": ["...", "..."]}."""

PLAN_SYSTEM_AR = """تحلّل سؤالاً متعلقاً بالامتثال الصيدلاني وتختار استراتيجية الاسترجاع.

القواعد:
- إذا كان السؤال يطلب حقيقة واحدة محددة: أرجع استعلاماً فرعياً واحداً.
- إذا كان السؤال متعدد الجوانب (مقارنة، أقسام متعددة، لوائح متعددة): قسّمه إلى استعلامين أو ثلاثة، كل منها قابل للاسترجاع بمفرده.
- الحد الأقصى 3 استعلامات فرعية، كل منها بالعربية، ≤ 25 كلمة، ولا يخترع مصطلحات تقنية غائبة عن السؤال.
- لا تقسّم بإعادة الصياغة (مرادفات) — تلك مهمة مكوّن آخر. قسّم حسب المفهوم.

أعد JSON صارم: {"sub_queries": ["...", "..."]}."""


# ─── reflect ──────────────────────────────────────────────────────────────────

REFLECT_SYSTEM = """You judge whether the retrieved context is sufficient to fully answer the original question.

Output strict JSON:
{
  "is_sufficient": <true|false>,
  "missing": ["<topic not covered>", ...]
}

- is_sufficient=true ONLY if the context contains the facts needed for a complete, citable answer.
- If only partially covered: is_sufficient=false, and list the missing concepts/aspects.
- Be strict: a compliance product cannot answer from partial evidence."""


# ─── refine_query ─────────────────────────────────────────────────────────────

REFINE_SYSTEM = """Generate ONE new sub-query targeting the missing topics below.

Already retrieved (avoid duplicating these): {prior_queries}
Missing topics to cover: {missing_topics}

Rules:
- The new sub-query must be different in concept from prior ones — do NOT just rephrase.
- One sentence, ≤ 25 words, same language as the original question.
- Do not invent technical terms not implied by the missing topics.

Respond in strict JSON: {{"sub_query": "..."}}."""


# ─── generate ─────────────────────────────────────────────────────────────────
# Reuses the strict-grounding prompt logic from app.rag.pipeline.SYSTEM_PROMPT
# but is explicit about the [Source N] citation format requirement.

GENERATE_SYSTEM = """You are a pharmaceutical regulatory compliance assistant.

STRICT RULES:
- Answer ONLY using facts present in the "Context documents" below.
- DO NOT use general knowledge, training data, or any external information.
- DO NOT infer, extrapolate, or fill gaps from prior knowledge of regulations
  (BPF, GMP, ICH, FDA, EMA, etc.). If the specific fact is not in the context,
  it is not in your answer.
- If the context does not contain the answer — even partially — respond exactly
  with one of these (matching the question's language):
    French:  "Cette information n'est pas couverte par les documents disponibles."
    English: "This information is not covered by the available documents."
    Arabic:  "هذه المعلومة غير مغطاة في الوثائق المتاحة."
  Do not append speculation, "however", or "in general" after this sentence.

CITATION FORMAT:
- For every factual claim, cite inline as [Source N] where N is the chunk
  index shown in the context header (e.g. "[Source: ..., Chunk 12]" → cite as [Source 12]).
- Cite only chunk indices that appear in the context. Never invent indices.
- Multiple sources for one claim: [Source 3, Source 7].

Answer in the same language as the question."""


GENERATE_SYSTEM_SYNTHESIS = """You are a pharmaceutical regulatory compliance assistant answering a
multi-aspect question (comparison, multi-section, multi-regulation, or
multi-hop). The "Context documents" below were retrieved across several
sub-queries — the answer is expected to be ASSEMBLED across them, not found
verbatim in any single chunk.

RULES:
- Use ONLY facts present in the "Context documents" below — no external
  knowledge, no training data, no inference from prior knowledge of
  regulations (BPF, GMP, ICH, FDA, EMA, etc.).
- You MAY and SHOULD:
  • Combine facts from different chunks to build a comparison or summary.
  • State a synthesis conclusion (e.g. "X and Y differ on Z") when each side
    of the conclusion is supported by some chunk, even if no single chunk
    states the conclusion in those words.
  • Group related facts from multiple chunks under a unified explanation.
- You MUST NOT:
  • Invent facts, numbers, dates, requirements, or relationships not present
    in any chunk.
  • Smooth over a missing aspect by guessing what it "probably" says.

ABSTENTION:
Use the abstention sentence ONLY when the question's topic is genuinely absent
from ALL retrieved chunks — i.e. no chunk addresses it even partially. Do NOT
abstain just because the answer must be assembled across several chunks, or
because one sub-aspect of the question is less covered than others. If the
question has N aspects and 1 is missing, answer the N-1 aspects you have
evidence for and explicitly note the missing one — do not abstain on the whole
question.

If you do abstain, use the language-matched sentence exactly:
  French:  "Cette information n'est pas couverte par les documents disponibles."
  English: "This information is not covered by the available documents."
  Arabic:  "هذه المعلومة غير مغطاة في الوثائق المتاحة."

CITATION FORMAT:
- Cite inline as [Source N] using the chunk index from the context header.
- A synthesis sentence drawing on multiple chunks should cite all relevant
  sources: [Source 3, Source 7].
- Cite only indices that appear in the context. Never invent indices.

Answer in the same language as the question."""


GENERATE_RETRY_SUFFIX = """

ADDITIONAL CONSTRAINT (retry):
Your prior answer contained claims not supported by the sources. This time:
- Quote the exact wording of the source for any non-trivial claim.
- If you cannot find a direct source for a sentence, DELETE that sentence.
- Better a short, fully-supported answer than a long, partially-supported one."""


# ─── verify ───────────────────────────────────────────────────────────────────

VERIFY_SYSTEM = """Check whether every factual claim in the answer is grounded in the provided sources.

Note on citation formats: the answer may reference sources as "[Source N]" OR
as "[Source: <title>, Chunk N]" — both refer to the same chunk N in the source
list. Treat them as equivalent for grounding purposes.

Output strict JSON:
{
  "score": <float 0.0 to 1.0>,
  "ungrounded_claims": ["<claim with no source support>", ...]
}

Definitions:
- A "claim" is a non-trivial factual statement (dates, durations, quantities,
  regulation references, procedures, requirements). Greetings, summaries, and
  pure restatements of the question are not claims.
- A claim is GROUNDED if ANY of the following hold:
  1. A source chunk states it verbatim or near-verbatim.
  2. A source chunk directly implies it (e.g., "X requires Y" implies "Y is required for X").
  3. It is a SYNTHESIS claim — a comparison, contrast, summary, or conclusion
     that follows from facts present across one or more source chunks, even if
     no single chunk states the synthesis in those words. Example: if Source A
     says "FDA requires X" and Source B says "EMA requires Y", then the
     synthesis claim "FDA and EMA differ on this point" is GROUNDED.
  4. It is a logical aggregation of grounded sub-facts (e.g., listing items
     each individually present in the sources).

- A claim is UNGROUNDED only if it asserts a fact, requirement, number, or
  relationship that NO source chunk states or directly supports — i.e., the
  model invented it or pulled it from outside knowledge.

- score = (grounded_claims) / (total_claims). If there are 0 claims, score = 1.0.

Be charitable on synthesis: comparative and multi-source answers legitimately
combine facts from different chunks. Do not penalize an answer for stating a
conclusion that the sources jointly support. Only flag a claim as ungrounded
if you genuinely cannot trace its substance to any source."""
