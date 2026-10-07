"""fal.ai-backed image-to-video (real queue API)."""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

import httpx

from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.video_generation.base import ImageToVideoProvider, ProgressCallback
from app.video_generation.models import VideoGenerationResult
from app.video_generation.replicate_provider import _download_video, _extract_video_url

FAL_QUEUE = "https://queue.fal.run"


class FalImageToVideoProvider(ImageToVideoProvider):
    name = "fal"

    def __init__(
        self,
        api_key: str,
        model: str = "fal-ai/minimax/video-01-live",
        *,
        timeout_seconds: float = 600.0,
        poll_interval_seconds: float = 2.0,
        output_dir: Path,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("FAL_KEY is not set.")
        self._key = api_key
        self.model = model
        self._timeout = timeout_seconds
        self._poll = poll_interval_seconds
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self._key}",
            "Content-Type": "application/json",
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
        mime = mime_type or "image/jpeg"
        data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        body: dict[str, Any] = {
            "prompt": motion_prompt,
            "image_url": data_uri,
            "prompt_optimizer": True,
        }
        # Kling on fal uses different field names
        if "kling" in self.model.lower():
            body = {
                "prompt": motion_prompt,
                "image_url": data_uri,
                "duration": "5",
                "aspect_ratio": "16:9",
            }
        await self._notify(on_progress, "generating", 35, "Submitting fal.ai image-to-video job…")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=self._timeout)) as client:
                submitted = await client.post(
                    f"{FAL_QUEUE}/{self.model}",
                    headers=self._headers(),
                    json=body,
                )
                if submitted.status_code >= 400:
                    raise ModelError(
                        f"fal.ai submit failed ({submitted.status_code}): {submitted.text[:400]}"
                    )
                ticket = submitted.json()
                status_url = ticket.get("status_url")
                response_url = ticket.get("response_url")
                if not status_url:
                    raise ModelError("fal.ai did not return a status_url.")
                elapsed = 0.0
                status = "IN_QUEUE"
                while status in {"IN_QUEUE", "IN_PROGRESS"}:
                    await self._notify(
                        on_progress,
                        "generating",
                        min(85, 40 + int(elapsed / max(self._timeout, 1) * 45)),
                        f"fal.ai status: {status}",
                    )
                    await asyncio.sleep(self._poll)
                    elapsed += self._poll
                    if elapsed > self._timeout:
                        raise ProviderTimeoutError("Image-to-video timed out waiting for fal.ai.")
                    polled = await client.get(status_url, headers=self._headers())
                    if polled.status_code >= 400:
                        raise ModelError(
                            f"fal.ai poll failed ({polled.status_code}): {polled.text[:400]}"
                        )
                    payload = polled.json()
                    status = payload.get("status", status)
                if status != "COMPLETED":
                    raise ModelError(f"fal.ai image-to-video failed with status={status}")
                result_resp = await client.get(response_url or status_url, headers=self._headers())
                if result_resp.status_code >= 400:
                    raise ModelError(
                        f"fal.ai result failed ({result_resp.status_code}): {result_resp.text[:400]}"
                    )
                result_json = result_resp.json()
                remote_url = _extract_video_url(result_json.get("video")) or _extract_video_url(
                    result_json
                )
                if isinstance(result_json.get("video"), dict):
                    remote_url = result_json["video"].get("url") or remote_url
                if not remote_url:
                    raise ModelError("fal.ai returned no video URL.")
                await self._notify(on_progress, "downloading", 90, "Downloading generated video…")
                request_id = ticket.get("request_id") or "fal_video"
                local_path, public_name = await _download_video(
                    client, remote_url, self._output_dir, str(request_id)
                )
        except (ModelError, ProviderTimeoutError, ProviderConfigurationError):
            raise
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Image-to-video request timed out.") from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"fal.ai image-to-video failed: {exc}") from exc

        await self._notify(on_progress, "ready", 100, "Video ready.")
        return VideoGenerationResult(
            provider=self.name,
            model=self.model,
            video_url=f"/api/v1/video/files/{public_name}",
            local_path=str(local_path),
            metadata={"remote_url": remote_url},
        )

    async def health_check(self) -> bool:
        return bool(self._key)
