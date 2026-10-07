"""The ``VisionProvider`` interface.
Architecture: ``Image -> VisionProvider -> structured analysis``. NEXA does
not implement its own vision model - every implementation is a thin adapter
over an existing multimodal model provider (mirrors the ``AIProvider``
pattern from Part 1's Model Gateway).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from app.vision.models import VisionAnalysisResult
SUPPORTED_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
)
class VisionProvider(ABC):
    """Abstract interface for an image-understanding backend."""
    name: str = "base"
    @abstractmethod
    async def analyze(
        self, image: bytes, mime_type: str, prompt: str | None = None
    ) -> VisionAnalysisResult:
        """Analyze ``image`` (raw bytes) and return a structured description.
        Args:
            image: Raw image bytes.
            mime_type: The image's MIME type, e.g. ``"image/png"``.
            prompt: Optional instruction guiding what to look for.
        Raises:
            app.models.errors.ModelError: If analysis fails.
            app.models.errors.ProviderTimeoutError: If the call times out.
        """
    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
