"""Select a real image-to-video provider from settings."""
from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.core.paths import resolve_under_project_root
from app.video_generation.base import ImageToVideoProvider
from app.video_generation.not_configured import NotConfiguredImageToVideoProvider


class ImageToVideoProviderFactory:
    @staticmethod
    def create(settings: Settings) -> ImageToVideoProvider:
        name = (settings.video_provider or "none").strip().lower()
        output_dir = resolve_under_project_root(settings.video_storage_dir)
        if name == "replicate" and settings.replicate_api_token:
            from app.video_generation.replicate_provider import ReplicateImageToVideoProvider

            return ReplicateImageToVideoProvider(
                api_token=settings.replicate_api_token,
                model=settings.replicate_i2v_model,
                timeout_seconds=settings.video_timeout_seconds,
                output_dir=Path(output_dir),
            )
        if name == "fal" and settings.fal_key:
            from app.video_generation.fal_provider import FalImageToVideoProvider

            return FalImageToVideoProvider(
                api_key=settings.fal_key,
                model=settings.fal_i2v_model,
                timeout_seconds=settings.video_timeout_seconds,
                output_dir=Path(output_dir),
            )
        return NotConfiguredImageToVideoProvider()
