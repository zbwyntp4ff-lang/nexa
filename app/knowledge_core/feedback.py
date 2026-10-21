"""Learning-loop feedback store — examples for evaluation, not auto fine-tuning."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.paths import resolve_under_project_root

_FEEDBACK_PATH = resolve_under_project_root("data/knowledge_core/feedback.jsonl")


FeedbackRating = Literal[
    "up",
    "down",
    "correct",
    "incorrect",
    "useful",
    "not_useful",
    "incomplete",
    "outdated",
    "factual_error",
    "code_error",
    "missing_sources",
    "off_topic",
]


class FeedbackEvent(BaseModel):
    """Evaluation sample — never auto-applies to model weights or system identity."""

    rating: FeedbackRating
    user_request: str = Field(..., min_length=1, max_length=4000)
    nexa_response: str = Field(..., min_length=1, max_length=20000)
    note: str | None = Field(default=None, max_length=2000)
    pack_ids: list[str] = Field(default_factory=list)
    intent: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    user_id: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def feedback_path() -> Path:
    return _FEEDBACK_PATH


def record_feedback(event: FeedbackEvent) -> FeedbackEvent:
    path = feedback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")
    return event


def recent_feedback(limit: int = 50, *, user_id: str | None = None) -> list[FeedbackEvent]:
    path = feedback_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[FeedbackEvent] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = FeedbackEvent.model_validate_json(line)
        except Exception:  # noqa: BLE001
            continue
        if user_id is not None and event.user_id != user_id:
            continue
        events.append(event)
    return events[-limit:]


def delete_feedback_for_user(user_id: str) -> int:
    """Rewrite feedback.jsonl without rows owned by ``user_id``."""
    path = feedback_path()
    if not path.exists():
        return 0
    kept: list[str] = []
    removed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            event = FeedbackEvent.model_validate_json(raw)
        except Exception:  # noqa: BLE001
            kept.append(raw)
            continue
        if event.user_id == user_id:
            removed += 1
            continue
        kept.append(raw)
    path.write_text(("\n".join(kept) + ("\n" if kept else "")), encoding="utf-8")
    return removed
