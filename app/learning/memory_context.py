"""Build a compact, user-scoped memory hint for chat (not fine-tuning)."""
from __future__ import annotations

from app.memory.manager import MemoryManager
from app.memory.models import MemoryType

_MAX_CHARS = 600
_MAX_ITEMS = 6


def build_memory_hint(
    manager: MemoryManager,
    *,
    user_id: str | None,
    query: str,
    enabled: bool = True,
) -> str | None:
    """Return a short system hint from long-term + preference memory.

    Confirmed preferences and long-term facts only. Conversation/short-term
    dumps are excluded to avoid stuffing the prompt. Secrets are already
    blocked at write time.
    """
    if not enabled or not user_id:
        return None
    results = manager.search(
        query=query or "",
        type=None,
        user_id=user_id,
        limit=20,
    )
    preferred: list[str] = []
    for hit in results:
        item = hit.item
        if item.type not in (MemoryType.LONG_TERM, MemoryType.USER_PREFERENCE):
            continue
        confidence = "preference" if item.type == MemoryType.USER_PREFERENCE else "fact"
        line = f"- [{confidence}] {item.content.strip()}"
        if line not in preferred:
            preferred.append(line)
        if len(preferred) >= _MAX_ITEMS:
            break
    if not preferred:
        # Fall back to recent preferences without query match.
        recent = manager.search(
            query="",
            type=MemoryType.USER_PREFERENCE,
            user_id=user_id,
            limit=_MAX_ITEMS,
        )
        for hit in recent:
            line = f"- [preference] {hit.item.content.strip()}"
            if line not in preferred:
                preferred.append(line)
    if not preferred:
        return None
    body = "\n".join(preferred)
    if len(body) > _MAX_CHARS:
        body = body[: _MAX_CHARS - 1] + "…"
    return (
        "User memory (approved facts/preferences only — not model weights):\n"
        f"{body}"
    )
