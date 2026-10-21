"""Build Engine data models (V1 + V2 BuildPlan)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.build.plan import BuildPlan, BuildStatus


class BuildStep(BaseModel):
    name: str
    status: Literal["ok", "skipped", "failed"] = "ok"
    detail: str = ""
    tool: str | None = None


class BuildProjectRecord(BaseModel):
    """Project memory for BUILD ENGINE — persisted workspace state (not a second Memory/RAG)."""

    project_id: str
    slug: str
    title: str
    kind: Literal["static_web", "node"] = "static_web"
    conversation_id: str | None = None
    #: Owner when created under authenticated API; required for cloud ACL.
    user_id: str | None = None
    root_rel: str
    entry_file: str = "index.html"
    files: list[str] = Field(default_factory=list)
    stack: str | None = None
    features: list[str] = Field(default_factory=list)
    preview_url: str | None = None
    known_errors: list[str] = Field(default_factory=list)
    plan: BuildPlan | None = None
    status: BuildStatus = "PLANNING"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BuildRunRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    project_id: str | None = None


class BuildRunResponse(BaseModel):
    success: bool
    mode: Literal["create", "edit"]
    project_id: str | None = None
    slug: str | None = None
    root_path: str | None = None
    files_created: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    preview_url: str | None = None
    steps: list[BuildStep] = Field(default_factory=list)
    message: str
    error: str | None = None
    # V2: user-safe plan snapshot (no chain-of-thought)
    plan: dict[str, Any] | None = None
    status: BuildStatus | None = None
    engine_version: str = "v2"
    # Evaluation Engine V1
    evaluation: dict[str, Any] | None = None
    improvement_attempts: int = 0
