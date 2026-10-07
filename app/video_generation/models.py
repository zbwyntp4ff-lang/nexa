"""Data models for NEXA image-to-video."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VideoJobPhase = Literal[
    "queued",
    "analyzing",
    "planning",
    "generating",
    "downloading",
    "ready",
    "failed",
]


class MotionPlan(BaseModel):
    """Natural-language motion brief sent to the video model."""

    scene_summary: str
    motion_prompt: str
    conservative: bool = True
    source: Literal["vision", "user", "default"] = "default"


class VideoGenerationResult(BaseModel):
    provider: str
    model: str
    video_url: str
    local_path: str | None = None
    duration_seconds: float | None = None
    motion_plan: MotionPlan | None = None
    metadata: dict = Field(default_factory=dict)


class VideoJobStatus(BaseModel):
    job_id: str
    phase: VideoJobPhase
    progress: int = Field(ge=0, le=100, default=0)
    message: str = ""
    intent: str = "IMAGE_TO_VIDEO"
    video_url: str | None = None
    provider: str | None = None
    model: str | None = None
    motion_plan: MotionPlan | None = None
    error: str | None = None
