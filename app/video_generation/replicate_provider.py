"""Replicate-backed image-to-video (real HTTP API, no fake output)."""
from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.video_generation.base import ImageToVideoProvider, ProgressCallback
from app.video_generation.models import VideoGenerationResult

REPLICATE_API = "https://api.replicate.com/v1"


class ReplicateImageToVideoProvider(ImageToVideoProvider):
    name = "replicate"

    def __init__(
        self,
        api_token: str,
        model: str = "kwaivgi/kling-v1.6-standard",
        *,
        timeout_seconds: float = 600.0,
        poll_interval_seconds: float = 2.5,
        output_dir: Path,
    ) -> None:
        if not api_token:
            raise ProviderConfigurationError("REPLICATE_API_TOKEN is not set.")
        self._token = api_token
        self.model = model
        self._timeout = timeout_seconds
        self._poll = poll_interval_seconds
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Prefer": "respond-async",
        }

    def _data_uri(self, image_bytes: bytes, mime_type: str) -> str:
        mime = mime_type or "image/jpeg"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _build_input(self, data_uri: str, motion_prompt: str) -> dict[str, Any]:
        # Kling-style models
        if "kling" in self.model.lower():
            return {
                "prompt": motion_prompt,
                "start_image": data_uri,
                "duration": 5,
                "aspect_ratio": "16:9",
            }
        # Minimax video-01
        if "minimax" in self.model.lower() or "video-01" in self.model.lower():
            return {
                "prompt": motion_prompt,
                "first_frame_image": data_uri,
                "prompt_optimizer": True,
            }
        # Stable Video Diffusion (image only; motion_prompt kept in metadata)
        if "stable-video" in self.model.lower() or "svd" in self.model.lower():
            return {
                "input_image": data_uri,
                "sizing_strategy": "maintain_aspect_ratio",
                "frames_per_second": 6,
                "motion_bucket_id": 40,
                "cond_aug": 0.02,
            }
        # Generic fallback used by many Replicate i2v models
        return {
            "prompt": motion_prompt,
            "image": data_uri,
            "input_image": data_uri,
            "start_image": data_uri,
        }

    async def _notify(
        self, on_progress: ProgressCallback | None, phase: str, progress: int, message: str
    ) -> None:
        if not on_progress:
            return
        result = on_progress(phase, progress, message)
        if asyncio.iscoroutine(result):
            await result

    async def generate(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        motion_prompt: str,
        on_progress: ProgressCallback | None = None,
    ) -> VideoGenerationResult:
        if not image_bytes:
            raise ModelError("Image bytes are empty.")
        data_uri = self._data_uri(image_bytes, mime_type)
        payload = {"input": self._build_input(data_uri, motion_prompt)}
        create_url = f"{REPLICATE_API}/models/{self.model}/predictions"
        await self._notify(on_progress, "generating", 35, "Submitting image-to-video job…")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=self._timeout)) as client:
                created = await client.post(create_url, headers=self._headers(), json=payload)
                if created.status_code >= 400:
                    raise ModelError(
                        f"Replicate create failed ({created.status_code}): {created.text[:400]}"
                    )
                prediction = created.json()
                get_url = prediction.get("urls", {}).get("get") or f"{REPLICATE_API}/predictions/{prediction['id']}"
                status = prediction.get("status", "starting")
                elapsed = 0.0
                while status in {"starting", "processing", "queued"}:
                    await self._notify(
                        on_progress,
                        "generating",
                        min(85, 40 + int(elapsed / max(self._timeout, 1) * 45)),
                        f"Replicate status: {status}",
                    )
                    await asyncio.sleep(self._poll)
                    elapsed += self._poll
                    if elapsed > self._timeout:
                        raise ProviderTimeoutError("Image-to-video timed out waiting for Replicate.")
                    polled = await client.get(get_url, headers=self._headers())
                    if polled.status_code >= 400:
                        raise ModelError(
                            f"Replicate poll failed ({polled.status_code}): {polled.text[:400]}"
                        )
                    prediction = polled.json()
                    status = prediction.get("status", status)
                if status != "succeeded":
                    err = prediction.get("error") or prediction.get("detail") or status
                    raise ModelError(f"Replicate image-to-video failed: {err}")
                output = prediction.get("output")
                remote_url = _extract_video_url(output)
                if not remote_url:
                    raise ModelError("Replicate returned no video URL.")
                await self._notify(on_progress, "downloading", 90, "Downloading generated video…")
                local_path, public_name = await _download_video(
                    client, remote_url, self._output_dir, prediction.get("id", "video")
                )
        except (ModelError, ProviderTimeoutError, ProviderConfigurationError):
            raise
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Image-to-video request timed out.") from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"Replicate image-to-video failed: {exc}") from exc

        await self._notify(on_progress, "ready", 100, "Video ready.")
        return VideoGenerationResult(
            provider=self.name,
            model=self.model,
            video_url=f"/api/v1/video/files/{public_name}",
            local_path=str(local_path),
            metadata={"remote_url": remote_url, "replicate_id": prediction.get("id")},
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{REPLICATE_API}/account",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False


def _extract_video_url(output: Any) -> str | None:
    if isinstance(output, str) and output.startswith("http"):
        return output
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str) and item.startswith("http"):
                return item
    if isinstance(output, dict):
        for key in ("video", "url", "output"):
            value = output.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
    return None


async def _download_video(
    client: httpx.AsyncClient, url: str, output_dir: Path, stem: str
) -> tuple[Path, str]:
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)[:64] or "video"
    ext = Path(url.split("?", 1)[0]).suffix or ".mp4"
    if ext.lower() not in {".mp4", ".webm", ".mov"}:
        ext = ".mp4"
    name = f"{safe_stem}{ext}"
    path = output_dir / name
    try:
        async with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise ModelError(f"Failed to download video ({resp.status_code}).")
            with path.open("wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)
    except BaseException:
        # Cancellation during account deletion or shutdown must not leave a
        # partial video artifact on disk.
        path.unlink(missing_ok=True)
        raise
    if path.stat().st_size < 64:
        raise ModelError("Downloaded video file is empty or corrupt.")
    return path, name
