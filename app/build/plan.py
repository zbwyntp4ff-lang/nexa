"""BuildPlan — internal execution contract for BUILD ENGINE V2."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.build.understanding import RequestUnderstanding

BuildStatus = Literal[
    "PLANNING",
    "SCAFFOLDING",
    "IMPLEMENTING",
    "BUILDING",
    "TESTING",
    "DEBUGGING",
    "IMPROVING",
    "READY",
    "FAILED",
]


class BuildTask(BaseModel):
    """Lightweight feature/task unit for large-project progress (no heavy orchestration)."""

    id: str
    title: str
    feature: str = ""
    status: Literal["pending", "in_progress", "done", "failed"] = "pending"


class BuildPlan(BaseModel):
    project_id: str
    name: str
    type: str
    goal: str
    requirements: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    stack: str = "html-css-js"
    architecture: str = "static_web"
    files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    tasks: list[BuildTask] = Field(default_factory=list)
    preview: str | None = None
    status: BuildStatus = "PLANNING"
    understanding: RequestUnderstanding | None = None
    slug: str | None = None
    root_rel: str | None = None
    entry_file: str = "index.html"
    debug_notes: list[str] = Field(default_factory=list)
    improved: list[str] = Field(default_factory=list)
    known_errors: list[str] = Field(default_factory=list)
    repair_attempts: int = 0
    max_repair_attempts: int = 3
    improvement_attempts: int = 0
    max_improvement_attempts: int = 3
    last_evaluation: dict | None = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def set_status(self, status: BuildStatus) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_tasks(self, status: Literal["pending", "in_progress", "done", "failed"]) -> None:
        for task in self.tasks:
            task.status = status


def tasks_from_features(features: list[str]) -> list[BuildTask]:
    tasks: list[BuildTask] = []
    for i, feature in enumerate(features or ["scaffold"]):
        tasks.append(
            BuildTask(
                id=f"task-{i + 1}",
                title=feature,
                feature=feature,
                status="pending",
            )
        )
    return tasks


def public_plan_summary(plan: BuildPlan) -> dict:
    """User-safe plan fields — no internal reasoning / CoT."""
    return {
        "project_id": plan.project_id,
        "name": plan.name,
        "type": plan.type,
        "goal": plan.goal,
        "stack": plan.stack,
        "architecture": plan.architecture,
        "files": list(plan.files),
        "features": list(plan.features),
        "tasks": [t.model_dump() for t in plan.tasks],
        "status": plan.status,
        "preview": plan.preview,
        "repair_attempts": plan.repair_attempts,
    }
