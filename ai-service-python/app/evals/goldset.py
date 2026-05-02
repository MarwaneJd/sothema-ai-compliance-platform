"""Goldset loader and schema.

A goldset is a JSON Lines file. Each line is one labeled query:

    {
      "id": "q-001",
      "query": "Quelle est la fréquence du contrôle microbiologique ?",
      "language": "fr",
      "intent": "lookup",
      "relevant_segment_ids": ["uuid-of-relevant-chunk", "..."],
      "reference_answer": "Le contrôle microbiologique est effectué chaque jour."
    }

`relevant_segment_ids` are `TextSegment.VectorStoreId` values (strings),
which is what the hybrid retriever returns. Use multiple ids when the
correct answer requires combining several chunks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Intent = Literal["definition", "procedure", "list", "comparison", "lookup", "multi_hop"]
Language = Literal["fr", "ar", "en"]

ALLOWED_INTENTS: frozenset[str] = frozenset(
    ["definition", "procedure", "list", "comparison", "lookup", "multi_hop"]
)
ALLOWED_LANGUAGES: frozenset[str] = frozenset(["fr", "ar", "en"])


@dataclass(frozen=True)
class GoldEntry:
    id: str
    query: str
    language: Language
    intent: Intent
    relevant_segment_ids: tuple[str, ...]
    reference_answer: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "GoldEntry":
        missing = [k for k in ("id", "query", "language", "intent", "relevant_segment_ids") if k not in raw]
        if missing:
            raise ValueError(f"Goldset entry missing required fields: {missing}; entry={raw}")
        if raw["language"] not in ALLOWED_LANGUAGES:
            raise ValueError(f"Bad language {raw['language']!r}; must be one of {sorted(ALLOWED_LANGUAGES)}")
        if raw["intent"] not in ALLOWED_INTENTS:
            raise ValueError(f"Bad intent {raw['intent']!r}; must be one of {sorted(ALLOWED_INTENTS)}")
        ids = raw["relevant_segment_ids"]
        if not isinstance(ids, list) or not ids:
            raise ValueError(f"relevant_segment_ids must be a non-empty list; got {ids!r}")
        return cls(
            id=str(raw["id"]),
            query=str(raw["query"]),
            language=raw["language"],
            intent=raw["intent"],
            relevant_segment_ids=tuple(str(x) for x in ids),
            reference_answer=str(raw.get("reference_answer", "")),
            notes=str(raw.get("notes", "")),
        )


def load_goldset(path: str | Path) -> list[GoldEntry]:
    """Load a JSONL goldset file. Skips blank lines and `#`-prefixed comments.

    Raises ValueError on the first malformed entry — fail loud during eval setup.
    """
    p = Path(path)
    if not p.exists():
        return []

    entries: list[GoldEntry] = []
    seen_ids: set[str] = set()
    with p.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise ValueError(f"{p}:{line_no}: invalid JSON — {e}") from e
            entry = GoldEntry.from_dict(raw)
            if entry.id in seen_ids:
                raise ValueError(f"{p}:{line_no}: duplicate goldset id {entry.id!r}")
            seen_ids.add(entry.id)
            entries.append(entry)
    return entries
