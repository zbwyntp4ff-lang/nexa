"""Project manifest — goal, stages, sources, files, verification (per user/project)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProjectStage(BaseModel):
    id: str
    name: str
    tool_name: str
    status: StageStatus = StageStatus.PENDING
    error: str | None = None
    verification: str | None = None
    result_summary: str | None = None
    file_id: str | None = None
    download_url: str | None = None
    retries: int = 0


class ProjectManifest(BaseModel):
    project_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str | None = None
    goal: str
    topic: str = ""
    status: ProjectStatus = ProjectStatus.PLANNING
    stages: list[ProjectStage] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    created_files: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_task_id: str | None = None
    partial: bool = False
    final_answer: str | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


class ManifestStore:
    """JSON manifests under ``<sandbox>/projects/<user_or_shared>/``."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _dir(self, user_id: str | None) -> Path:
        # Isolate by user when known; otherwise shared local bucket.
        bucket = user_id or "_local"
        safe = "".join(c for c in bucket if c.isalnum() or c in "-_")[:64] or "_local"
        path = self._root / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, manifest: ProjectManifest) -> Path:
        manifest.touch()
        path = self._dir(manifest.user_id) / f"{manifest.project_id}.json"
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return path

    def get(self, project_id: str, *, user_id: str | None = None) -> ProjectManifest | None:
        # Prefer user bucket, then fall back to _local for unauthenticated runs.
        candidates = []
        if user_id:
            candidates.append(self._dir(user_id) / f"{project_id}.json")
        candidates.append(self._dir(None) / f"{project_id}.json")
        if user_id:
            # Do not leak other users' manifests: only scan own + local.
            pass
        else:
            # When no user, only local.
            candidates = [self._dir(None) / f"{project_id}.json"]
        for path in candidates:
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    man = ProjectManifest.model_validate(data)
                    if user_id and man.user_id and man.user_id != user_id:
                        return None
                    return man
                except Exception:  # noqa: BLE001
                    continue
        return None
