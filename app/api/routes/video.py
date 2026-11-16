"""Image-to-video API — real provider jobs with progress polling."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import get_image_to_video_service
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root
from app.models.errors import ModelError
from app.video_generation.intent import detects_image_to_video
from app.video_generation.models import VideoJobStatus
from app.video_generation.service import ImageToVideoService, get_video_job_store

router = APIRouter(prefix="/api/v1", tags=["video"])
_Auth = Annotated[UserRecord | None, Depends(require_user_when_enforced)]


class ImageToVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    attachment_ids: list[str] = Field(..., min_length=1)
    force: bool = False


class IntentDetectRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    has_image: bool = False


@router.post("/video/intent")
async def detect_intent(body: IntentDetectRequest) -> dict:
    matched = body.has_image and detects_image_to_video(body.prompt)
    return {"intent": "IMAGE_TO_VIDEO" if matched else None, "matched": matched}


@router.post("/video/image-to-video", response_model=VideoJobStatus)
async def start_image_to_video(
    body: ImageToVideoRequest,
    service: Annotated[ImageToVideoService, Depends(get_image_to_video_service)],
    user: _Auth = None,
) -> VideoJobStatus:
    return await service.start_job(
        attachment_ids=body.attachment_ids,
        prompt=body.prompt,
        user_id=user.id if user is not None else None,
        force=body.force or detects_image_to_video(body.prompt),
    )


@router.get("/video/jobs/{job_id}", response_model=VideoJobStatus)
async def get_video_job(job_id: str, user: _Auth = None) -> VideoJobStatus:
    settings = get_settings()
    status = await get_video_job_store().get(
        job_id, user_id=user.id if user is not None else None, enforce=settings.tokens_enforce
    )
    if status is None:
        raise ModelError(f"Unknown video job '{job_id}'.")
    return status


@router.get("/video/files/{filename}")
async def get_video_file(filename: str) -> FileResponse:
    settings = get_settings()
    root = resolve_under_project_root(settings.video_storage_dir).resolve()
    candidate = (root / Path(filename).name).resolve()
    if root not in candidate.parents and candidate != root:
        raise ModelError("Invalid video path.")
    if not candidate.is_file():
        raise ModelError("Video file not found.")
    media = "video/mp4"
    if candidate.suffix.lower() == ".webm":
        media = "video/webm"
    elif candidate.suffix.lower() == ".mov":
        media = "video/quicktime"
    return FileResponse(candidate, media_type=media, filename=candidate.name)
