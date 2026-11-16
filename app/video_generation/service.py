"""In-memory image-to-video job tracker + orchestration."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from app.attachments.manager import AttachmentManager
from app.billing.entitlements import EntitlementService
from app.billing.errors import EntitlementDeniedError
from app.config.settings import Settings
from app.models.errors import AttachmentNotFoundError, ModelError, ProviderConfigurationError
from app.video_generation.base import ImageToVideoProvider
from app.video_generation.intent import detects_image_to_video
from app.video_generation.models import MotionPlan, VideoJobStatus
from app.video_generation.motion import build_motion_plan


@dataclass
class _Job:
    status: VideoJobStatus
    user_id: str | None = None
    task: asyncio.Task | None = None


class VideoJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_id: str, status: VideoJobStatus, *, user_id: str | None = None) -> VideoJobStatus:
        async with self._lock:
            self._jobs[job_id] = _Job(status=status, user_id=user_id)
        return status

    async def update(self, job_id: str, **fields) -> VideoJobStatus:
        async with self._lock:
            job = self._jobs[job_id]
            data = job.status.model_dump()
            data.update(fields)
            job.status = VideoJobStatus(**data)
            return job.status

    async def get(self, job_id: str, *, user_id: str | None = None, enforce: bool = False) -> VideoJobStatus | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if enforce and (user_id is None or job.user_id != user_id):
                return None
            if user_id is not None and job.user_id != user_id:
                return None
            return job.status

    async def can_access_file(self, filename: str, *, user_id: str | None = None, enforce: bool = False) -> bool:
        """Allow access only when a job owned by the caller references this file."""
        from urllib.parse import urlparse
        async with self._lock:
            for job in self._jobs.values():
                video_url = job.status.video_url or ""
                if Path(urlparse(video_url).path).name != filename:
                    continue
                if enforce and (user_id is None or job.user_id != user_id):
                    return False
                if user_id is not None and job.user_id != user_id:
                    return False
                return True
        return False

    async def attach_task(self, job_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].task = task


_STORE = VideoJobStore()


def get_video_job_store() -> VideoJobStore:
    return _STORE


class ImageToVideoService:
    def __init__(
        self,
        *,
        settings: Settings,
        provider: ImageToVideoProvider,
        attachments: AttachmentManager,
        entitlements: EntitlementService | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._attachments = attachments
        self._entitlements = entitlements
        self._store = get_video_job_store()

    async def start_job(
        self,
        *,
        attachment_ids: list[str],
        prompt: str,
        user_id: str | None = None,
        force: bool = False,
    ) -> VideoJobStatus:
        if not force and not detects_image_to_video(prompt):
            raise ModelError("Message does not look like an image-to-video request.")
        if not attachment_ids:
            raise ModelError("Attach an image to animate.")
        if not self._attachments.has_images(attachment_ids, user_id=user_id):
            raise ModelError("IMAGE_TO_VIDEO requires at least one image attachment.")

        if self._entitlements and user_id and self._settings.video_require_entitlement:
            if not self._entitlements.can_use_feature(user_id, "image_to_video"):
                raise EntitlementDeniedError(
                    "Plan does not include image-to-video. Upgrade in Pricing / Billing."
                )

        job_id = uuid.uuid4().hex
        status = VideoJobStatus(
            job_id=job_id,
            phase="queued",
            progress=1,
            message="Queued image-to-video job",
            intent="IMAGE_TO_VIDEO",
        )
        await self._store.create(job_id, status, user_id=user_id)
        task = asyncio.create_task(self._run(job_id, attachment_ids, prompt, user_id))
        await self._store.attach_task(job_id, task)
        return status

    async def _run(self, job_id: str, attachment_ids: list[str], prompt: str, user_id: str | None) -> None:
        try:
            await self._store.update(
                job_id, phase="analyzing", progress=10, message="Analyzing image…"
            )
            payloads = self._attachments.image_payloads(attachment_ids, user_id=user_id)
            if not payloads:
                raise AttachmentNotFoundError(attachment_ids[0] if attachment_ids else "unknown")
            image_bytes, mime_type = payloads[0]

            await self._store.update(
                job_id, phase="planning", progress=25, message="Creating motion plan…"
            )
            plan: MotionPlan = await build_motion_plan(
                settings=self._settings,
                image_bytes=image_bytes,
                mime_type=mime_type,
                user_text=prompt,
            )
            await self._store.update(job_id, motion_plan=plan, progress=30)

            async def on_progress(phase: str, progress: int, message: str) -> None:
                await self._store.update(
                    job_id, phase=phase, progress=progress, message=message  # type: ignore[arg-type]
                )

            result = await self._provider.generate(
                image_bytes=image_bytes,
                mime_type=mime_type,
                motion_prompt=plan.motion_prompt,
                on_progress=on_progress,
            )
            result.motion_plan = plan
            await self._store.update(
                job_id,
                phase="ready",
                progress=100,
                message="Video ready",
                video_url=result.video_url,
                provider=result.provider,
                model=result.model,
                motion_plan=plan,
                error=None,
            )
        except (ProviderConfigurationError, EntitlementDeniedError, ModelError, AttachmentNotFoundError) as exc:
            await self._store.update(
                job_id,
                phase="failed",
                progress=100,
                message=str(exc),
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            await self._store.update(
                job_id,
                phase="failed",
                progress=100,
                message="Image-to-video failed.",
                error=str(exc),
            )
