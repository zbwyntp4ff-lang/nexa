"""Image generation endpoint - backs Create mode in the frontend."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.api.deps import (
    get_auth_service,
    get_image_generation_provider,
    get_settings,
    get_token_service,
)
from app.api.routes.auth import _extract_token
from app.auth.errors import UnauthorizedError
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import Settings
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.models import ImageGenerationResult
from app.tokens.guard import resolve_request_id, run_with_token_charge
from app.tokens.service import TokenService

router = APIRouter(prefix="/api/v1", tags=["image"])
_bearer = HTTPBearer(auto_error=False)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="What to draw.")
    size: str = Field(default="1024x1024", description="Provider-specific size, e.g. '1024x1024'.")
    request_id: str | None = Field(default=None, description="Idempotency key for token charging.")


def _resolve_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRecord | None:
    token = _extract_token(request, credentials)
    if not token:
        if settings.tokens_enforce:
            raise UnauthorizedError()
        return None
    try:
        return auth.get_user_for_token(token)
    except UnauthorizedError:
        if settings.tokens_enforce:
            raise
        return None


@router.post("/image/generate", response_model=ImageGenerationResult)
async def generate_image(
    request: ImageGenerateRequest,
    provider: ImageGenerationProvider = Depends(get_image_generation_provider),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    user: UserRecord | None = Depends(_resolve_user),
    x_request_id: Annotated[str | None, Header()] = None,
) -> ImageGenerationResult:
    async def _work() -> ImageGenerationResult:
        return await provider.generate(request.prompt, size=request.size)

    if user is None or not settings.tokens_enforce:
        return await _work()

    rid = resolve_request_id(request.request_id, x_request_id)
    return await run_with_token_charge(
        tokens,
        user_id=user.id,
        amount=tokens.cost_image,
        request_id=rid,
        reason="image_generate",
        work=_work,
    )
