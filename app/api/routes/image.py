"""Image generation endpoint - backs Create mode in the frontend.

Deliberately thin: validation + delegation to whichever
:class:`app.image_generation.base.ImageGenerationProvider` is configured.
When no real provider is configured, the dependency returns
``NotConfiguredImageGenerationProvider``, which raises a clear
``ProviderConfigurationError`` (mapped to HTTP 503) instead of a silent
failure or a fabricated image.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_image_generation_provider
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.models import ImageGenerationResult

router = APIRouter(prefix="/api/v1", tags=["image"])


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="What to draw.")
    size: str = Field(default="1024x1024", description="Provider-specific size, e.g. '1024x1024'.")


@router.post("/image/generate", response_model=ImageGenerationResult)
async def generate_image(
    request: ImageGenerateRequest,
    provider: ImageGenerationProvider = Depends(get_image_generation_provider),
) -> ImageGenerationResult:
    return await provider.generate(request.prompt, size=request.size)
