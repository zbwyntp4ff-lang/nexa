"""Image-to-video API — real provider jobs with progress polling."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, get_image_to_video_service
from app.api.routes.auth import _extract_token
from app.auth.errors import UnauthorizedError
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root
from app.models.errors import ModelError
from app.video_generation.intent import detects_image_to_video
from app.video_generation.models import VideoJobStatus
from app.video_generation.service import ImageToVideoService, get_video_job_store

router = APIRouter(prefix="/api/v1", tags=["video"])
_bearer = HTTPBearer(auto_error=False)


class ImageToVideoRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    attachment_ids: list[str] = Field(..., min_length=1)
    force: bool = False


class IntentDetectRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    has_image: bool = False


def _optional_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> str | None:
    token = _extract_token(request, credentials)
    if not token:
        return None
    try:
        return auth.get_user_for_token(token).id
    except UnauthorizedError:
        return None


@router.post("/video/intent")
async def detect_intent(body: IntentDetectRequest) -> dict:
    matched = body.has_image and detects_image_to_video(body.prompt)
    return {"intent": "IMAGE_TO_VIDEO" if matched else None, "matched": matched}


@router.post("/video/image-to-video", response_model=VideoJobStatus)
async def start_image_to_video(
    body: ImageToVideoRequest,
    user_id: Annotated[str | None, Depends(_optional_user_id)],
    service: Annotated[ImageToVideoService, Depends(get_image_to_video_service)],
) -> VideoJobStatus:
    return await service.start_job(
        attachment_ids=body.attachment_ids,
        prompt=body.prompt,
        user_id=user_id,
        force=body.force or detects_image_to_video(body.prompt),
    )


@router.get("/video/jobs/{job_id}", response_model=VideoJobStatus)
async def get_video_job(job_id: str) -> VideoJobStatus:
    status = await get_video_job_store().get(job_id)
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
