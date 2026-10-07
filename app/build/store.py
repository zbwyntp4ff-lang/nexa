"""Persist active BUILD_PROJECT workspaces (JSON, not a second RAG)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.build.models import BuildProjectRecord
from app.core.paths import resolve_under_project_root

_STORE = resolve_under_project_root("data/build_projects.json")


def _load() -> dict:
    if not _STORE.exists():
        return {"projects": {}, "by_conversation": {}}
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"projects": {}, "by_conversation": {}}


def _save(data: dict) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_project(record: BuildProjectRecord) -> BuildProjectRecord:
    data = _load()
    record.updated_at = datetime.now(timezone.utc).isoformat()
    data.setdefault("projects", {})[record.project_id] = record.model_dump()
    if record.conversation_id:
        data.setdefault("by_conversation", {})[record.conversation_id] = record.project_id
    _save(data)
    return record


def get_project(project_id: str) -> BuildProjectRecord | None:
    raw = _load().get("projects", {}).get(project_id)
    return BuildProjectRecord.model_validate(raw) if raw else None


def get_project_for_conversation(conversation_id: str | None) -> BuildProjectRecord | None:
    if not conversation_id:
        return None
    data = _load()
    pid = data.get("by_conversation", {}).get(conversation_id)
    if not pid:
        return None
    return get_project(pid)


def list_projects() -> list[BuildProjectRecord]:
    return [BuildProjectRecord.model_validate(v) for v in _load().get("projects", {}).values()]


def workspace_root() -> Path:
    from app.config.settings import get_settings

    root = resolve_under_project_root(get_settings().agent_workspace_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root
