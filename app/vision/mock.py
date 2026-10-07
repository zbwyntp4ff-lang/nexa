"""A deterministic, dependency-free vision provider for local development and tests."""
from __future__ import annotations
from app.models.errors import ModelError
from app.vision.base import VisionProvider
from app.vision.models import VisionAnalysisResult
class MockVisionProvider(VisionProvider):
    name = "mock"
    def __init__(self, model_name: str = "nexa-vision-mock-1") -> None:
        self._model_name = model_name
    async def analyze(
        self, image: bytes, mime_type: str, prompt: str | None = None
    ) -> VisionAnalysisResult:
        if not image:
            raise ModelError("Image data must not be empty.")
        if not mime_type:
            raise ModelError("mime_type must be provided.")
        description = (
            f"[mock:{self._model_name}] Received a {len(image)}-byte {mime_type} image."
        )
        if prompt:
            description += f" Prompt: {prompt}"
        return VisionAnalysisResult(
            description=description,
            provider=self.name,
            model=self._model_name,
            tags=["mock-analysis"],
            raw={"byte_size": len(image), "mime_type": mime_type, "prompt": prompt},
        )
    async def health_check(self) -> bool:
        return True
