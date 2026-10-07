"""Learning-loop feedback store — examples for evaluation, not auto fine-tuning."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.paths import resolve_under_project_root

_FEEDBACK_PATH = resolve_under_project_root("data/knowledge_core/feedback.jsonl")


class FeedbackEvent(BaseModel):
    rating: Literal["up", "down", "correct", "incorrect"]
    user_request: str = Field(..., min_length=1, max_length=4000)
    nexa_response: str = Field(..., min_length=1, max_length=20000)
    note: str | None = Field(default=None, max_length=2000)
    pack_ids: list[str] = Field(default_factory=list)
    intent: str | None = None
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


def recent_feedback(limit: int = 50) -> list[FeedbackEvent]:
    path = feedback_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[FeedbackEvent] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(FeedbackEvent.model_validate_json(line))
        except Exception:  # noqa: BLE001
            continue
    return events
