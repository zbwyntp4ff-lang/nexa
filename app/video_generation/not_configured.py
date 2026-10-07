"""Honest not-configured provider — never fabricates video."""
from __future__ import annotations

from app.models.errors import ProviderConfigurationError
from app.video_generation.base import ImageToVideoProvider, ProgressCallback
from app.video_generation.models import VideoGenerationResult

NOT_CONFIGURED_MESSAGE = (
    "Image-to-video provider is not configured. "
    "Set VIDEO_PROVIDER=replicate and REPLICATE_API_TOKEN (or VIDEO_PROVIDER=fal and FAL_KEY) in .env."
)


class NotConfiguredImageToVideoProvider(ImageToVideoProvider):
    name = "none"
    model = "none"

    async def generate(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        motion_prompt: str,
        on_progress: ProgressCallback | None = None,
    ) -> VideoGenerationResult:
        raise ProviderConfigurationError(NOT_CONFIGURED_MESSAGE)

    async def health_check(self) -> bool:
        return False
