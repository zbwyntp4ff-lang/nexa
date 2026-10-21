"""Detect conflicting long-term memory items for the same user (heuristic)."""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.memory.manager import MemoryManager
from app.memory.models import MemoryItem, MemoryType

_NEGATION = re.compile(
    r"\b(not|no|never|isn't|aren't|doesn't|don't|won't|cannot|can't|не|нет|никогда)\b",
    re.I,
)


class ContradictionHit(BaseModel):
    existing_id: str
    existing_content: str
    new_content: str
    reason: str


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zа-яё0-9_]{3,}", text.lower()) if t}


def find_contradictions(
    manager: MemoryManager,
    *,
    user_id: str | None,
    content: str,
    type: MemoryType = MemoryType.LONG_TERM,
) -> list[ContradictionHit]:
    """Flag likely conflicts: shared key tokens + opposing polarity.

    Conservative: returns candidates for UI review, never auto-deletes.
    """
    if not user_id or not content.strip():
        return []
    new_toks = _tokens(content)
    if len(new_toks) < 2:
        return []
    new_neg = bool(_NEGATION.search(content))
    hits: list[ContradictionHit] = []
    results = manager.search(query="", type=type, user_id=user_id, limit=200)
    for hit in results:
        item: MemoryItem = hit.item
        old_toks = _tokens(item.content)
        overlap = new_toks & old_toks
        if len(overlap) < 2:
            continue
        old_neg = bool(_NEGATION.search(item.content))
        if new_neg != old_neg and overlap:
            hits.append(
                ContradictionHit(
                    existing_id=item.id,
                    existing_content=item.content,
                    new_content=content,
                    reason=f"Shared terms {sorted(overlap)[:5]} with opposite polarity",
                )
            )
    return hits
