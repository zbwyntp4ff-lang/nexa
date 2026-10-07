"""Image-to-video provider interface — real APIs only."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.video_generation.models import VideoGenerationResult

ProgressCallback = Callable[[str, int, str], Awaitable[None] | None]


class ImageToVideoProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def generate(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        motion_prompt: str,
        on_progress: ProgressCallback | None = None,
    ) -> VideoGenerationResult:
        """Generate a real video from an image + motion prompt.

        Raises:
            ProviderConfigurationError: provider/API key missing.
            ModelError / ProviderTimeoutError: upstream failure.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        ...
