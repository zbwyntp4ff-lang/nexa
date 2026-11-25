"""User-controllable Learning & Memory toggles (JSON file, not secrets)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.paths import resolve_under_project_root

_PATH = resolve_under_project_root("data/learning_settings.json")
_LOCK = threading.Lock()


class LearningSettings(BaseModel):
    """Product toggles — never claims fine-tuning is on."""

    memory_enabled: bool = True
    """Inject long-term / preference memory into chat context when true."""
    feedback_enabled: bool = True
    """Allow storing answer ratings."""
    auto_knowledge_base: bool = True
    """Default RAG opt-in for chat when Knowledge Base has documents."""
    allow_cloud_on_documents: bool = False
    """When false, document context is sent only to local models.

    Cloud routing and cloud fallback are blocked for requests containing
    attachments or retrieved Knowledge Base document context. If no local
    model is available, the request fails closed instead of sending the
    document to a cloud provider.
    """
    last_index_at: str | None = None
    last_eval_at: str | None = None
    last_eval_summary: str | None = None
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _path() -> Path:
    return _PATH


def get_learning_settings() -> LearningSettings:
    path = _path()
    if not path.exists():
        return LearningSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LearningSettings.model_validate(raw)
    except Exception:  # noqa: BLE001
        return LearningSettings()


def save_learning_settings(settings: LearningSettings) -> LearningSettings:
    settings.updated_at = datetime.now(timezone.utc).isoformat()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        path.write_text(
            json.dumps(settings.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return settings
