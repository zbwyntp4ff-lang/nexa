"""Project manifest — goal, stages, sources, files, verification (per user/project)."""
from __future__ import annotations

import json
import re
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
    """JSON manifests under the projects/<user_or_shared>/ directory."""

    _USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
    _PROJECT_ID_RE = __import__("re").compile(r"^[0-9a-f]{32}$")

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _dir(self, user_id: str | None) -> Path:
        """Return one exact tenant bucket; never normalize IDs into collisions."""
        if user_id is None:
            bucket = "_local"
        else:
            uid = str(user_id).strip()
            if not self._USER_ID_RE.fullmatch(uid):
                raise ValueError("Invalid project owner identifier.")
            bucket = uid
        path = (self._root / bucket).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("Project owner directory escapes storage root.") from exc
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, manifest: ProjectManifest) -> Path:
        manifest.touch()
        if not self._PROJECT_ID_RE.fullmatch(manifest.project_id):
            raise ValueError("Invalid project identifier.")
        path = self._dir(manifest.user_id) / f"{manifest.project_id}.json"
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return path

    def get(self, project_id: str, *, user_id: str | None = None) -> ProjectManifest | None:
        """Load only from the caller's exact bucket.

        Authenticated users never fall back to the shared local bucket: doing
        so could expose ownerless manifests created by a desktop/local session.
        """
        if not self._PROJECT_ID_RE.fullmatch(project_id):
            return None
        path = self._dir(user_id) / f"{project_id}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            man = ProjectManifest.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return None
        if man.user_id != user_id:
            return None
        return man
