"""Build observability — only events that the engine actually emits."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.logging_config import get_logger

logger = get_logger("nexa.build.events")

BuildEventType = Literal[
    "BUILD_STARTED",
    "PLAN_CREATED",
    "PROJECT_CREATED",
    "FILE_CREATED",
    "FILE_UPDATED",
    "BUILD_SUCCEEDED",
    "BUILD_FAILED",
    "TEST_STARTED",
    "TEST_SUCCEEDED",
    "TEST_FAILED",
    "REPAIR_STARTED",
    "REPAIR_COMPLETED",
    "PREVIEW_STARTED",
    "PREVIEW_READY",
    "EVALUATION_STARTED",
    "EVALUATION_COMPLETED",
    "RUNTIME_VERIFICATION_STARTED",
    "RUNTIME_VERIFICATION_COMPLETED",
    "IMPROVEMENT_STARTED",
    "IMPROVEMENT_COMPLETED",
    "BUILD_COMPLETED",
]

_MAX_BUFFER = 200
_EVENTS: list["BuildEvent"] = []


class BuildEvent(BaseModel):
    type: BuildEventType
    project_id: str | None = None
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def emit(
    event_type: BuildEventType,
    *,
    project_id: str | None = None,
    detail: str = "",
    **data: Any,
) -> BuildEvent:
    event = BuildEvent(type=event_type, project_id=project_id, detail=detail, data=data)
    _EVENTS.append(event)
    if len(_EVENTS) > _MAX_BUFFER:
        del _EVENTS[: len(_EVENTS) - _MAX_BUFFER]
    logger.info(
        "build_event type=%s project=%s detail=%s",
        event_type,
        project_id,
        detail[:120],
    )
    return event


def recent_events(*, project_id: str | None = None, limit: int = 50) -> list[BuildEvent]:
    items = _EVENTS if project_id is None else [e for e in _EVENTS if e.project_id == project_id]
    return items[-limit:]


def clear_events_for_tests() -> None:
    _EVENTS.clear()
