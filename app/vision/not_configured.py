"""Default vision provider when no real multimodal backend is configured.

Does **not** fabricate a fake image analysis — reports clearly that vision
is unavailable so the UI/API can surface a configuration error.
"""
from __future__ import annotations
from app.models.errors import ProviderConfigurationError
from app.vision.base import VisionProvider
from app.vision.models import VisionAnalysisResult

NOT_CONFIGURED_MESSAGE = "Vision provider is not configured."


class NotConfiguredVisionProvider(VisionProvider):
    name = "none"

    async def analyze(
        self, image: bytes, mime_type: str, prompt: str | None = None
    ) -> VisionAnalysisResult:
        raise ProviderConfigurationError(NOT_CONFIGURED_MESSAGE)

    async def health_check(self) -> bool:
        return False
