"""In-memory image-to-video job tracker + orchestration."""
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

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
    """Tracks jobs and persists owner/status metadata for restart-safe access."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._jobs: dict[str, _Job] = {}
        self._lock = asyncio.Lock()
        self._storage_dir: Path | None = None
        self._manifest_path: Path | None = None
        if storage_dir is not None:
            self.configure_storage(storage_dir)

    def configure_storage(self, storage_dir: Path) -> None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        resolved_dir = storage_dir.resolve()
        manifest_path = resolved_dir / ".nexa_video_jobs.json"
        if self._manifest_path == manifest_path:
            return
        loaded: dict[str, _Job] = {}
        if manifest_path.is_symlink():
            raise RuntimeError("Video job manifest must not be a symlink.")
        if manifest_path.exists():
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    raise ValueError("video job manifest must be a list")
                for item in raw:
                    if not isinstance(item, dict):
                        raise ValueError("invalid video job manifest entry")
                    status = VideoJobStatus.model_validate(item["status"])
                    job_id = status.job_id
                    if not job_id or job_id in loaded:
                        raise ValueError("invalid or duplicate video job id")
                    user_id = item.get("user_id")
                    if user_id is not None and not isinstance(user_id, str):
                        raise ValueError("invalid video job owner")
                    if status.phase == "ready":
                        filename = Path(urlparse(status.video_url or "").path).name
                        local_path = resolved_dir / filename if filename else None
                        if (
                            not status.video_url
                            or not re.fullmatch(r"[A-Za-z0-9._-]{1,255}", filename)
                            or filename in {".", ".."}
                            or urlparse(status.video_url).path != f"/api/v1/video/files/{filename}"
                            or status.video_url != f"/api/v1/video/files/{filename}"
                            or local_path is None
                            or not local_path.is_file()
                            or local_path.is_symlink()
                        ):
                            status = status.model_copy(update={
                                "phase": "failed",
                                "progress": 100,
                                "message": "Video result is unavailable after a server restart.",
                                "video_url": None,
                            })
                    if status.phase not in {"ready", "failed"}:
                        status = status.model_copy(update={
                            "phase": "failed",
                            "progress": 100,
                            "message": "Generation was interrupted by a server restart.",
                            "video_url": None,
                        })
                    loaded[job_id] = _Job(status=status, user_id=user_id)
            except Exception as exc:
                raise RuntimeError(
                    "Video job manifest is invalid; refusing to overwrite it."
                ) from exc
        self._storage_dir = resolved_dir
        self._manifest_path = manifest_path
        self._jobs.clear()
        self._jobs.update(loaded)
        if manifest_path.exists():
            self._persist()
        retained_files = {
            Path(urlparse(job.status.video_url or "").path).name
            for job in self._jobs.values()
            if job.status.phase == "ready" and job.status.video_url
        }
        # Remove generated video files whose owner/job manifest was lost in a crash.
        for extension in ("mp4", "webm", "mov"):
            for candidate in resolved_dir.glob(f"*.{extension}"):
                if candidate.name not in retained_files:
                    candidate.unlink(missing_ok=True)

    def _persist(self) -> None:
        if self._manifest_path is None:
            return
        # Persist only operational metadata. User prompts, image descriptions,
        # and provider error details are intentionally excluded.
        entries = []
        for job_id, job in self._jobs.items():
            current = job.status
            message = (
                "Video ready" if current.phase == "ready"
                else "Video generation failed."
            )
            video_url = current.video_url
            parsed = urlparse(video_url or "")
            filename = Path(parsed.path).name
            is_local_result = (
                parsed.path.startswith("/api/v1/video/files/")
                and bool(re.fullmatch(r"[A-Za-z0-9._-]{1,255}", filename))
                and filename not in {".", ".."}
                and parsed.path == f"/api/v1/video/files/{filename}"
                and video_url == f"/api/v1/video/files/{filename}"
                and not parsed.query
                and not parsed.fragment
            )
            if current.phase == "ready" and not is_local_result:
                # Do not persist provider-signed URLs or remote credentials.
                message = "Video result is unavailable after a server restart."
                safe_phase = "failed"
                video_url = None
                progress = 100
            else:
                safe_phase = current.phase
                progress = current.progress
                if safe_phase not in {"ready", "failed"}:
                    message = "Generation was interrupted by a server restart."
            status = VideoJobStatus(
                job_id=job_id,
                phase=safe_phase,
                progress=progress,
                message=message,
                intent=current.intent,
                video_url=video_url if is_local_result else None,
                provider=current.provider,
                model=current.model,
            )
            entries.append({
                "user_id": job.user_id,
                "status": status.model_dump(mode="json"),
            })
        temporary = self._manifest_path.with_name(self._manifest_path.name + ".tmp")
        temporary.write_text(
            json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, self._manifest_path)

    def _delete_local_video(
        self, video_url: str | None, storage_dir: Path | None = None
    ) -> None:
        root = storage_dir.resolve() if storage_dir is not None else self._storage_dir
        if root is None or not video_url:
            return
        parsed = urlparse(video_url)
        filename = Path(parsed.path).name
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or parsed.path != f"/api/v1/video/files/{filename}"
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,255}", filename)
            or filename in {".", ".."}
        ):
            return
        candidate = root / filename
        if candidate.is_symlink():
            candidate.unlink(missing_ok=True)
            return
        resolved = candidate.resolve()
        if resolved != root and root in resolved.parents and resolved.is_file():
            resolved.unlink(missing_ok=True)

    async def create(self, job_id: str, status: VideoJobStatus, *, user_id: str | None = None) -> VideoJobStatus:
        if status.job_id != job_id:
            raise ValueError("video job id does not match status")
        async with self._lock:
            if job_id in self._jobs:
                raise ValueError("video job already exists")
            self._jobs[job_id] = _Job(status=status, user_id=user_id)
            self._persist()
        return status

    async def update(self, job_id: str, **fields) -> VideoJobStatus:
        async with self._lock:
            job = self._jobs[job_id]
            data = job.status.model_dump()
            data.update(fields)
            job.status = VideoJobStatus(**data)
            self._persist()
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
                if urlparse(video_url).path.rsplit("/", 1)[-1] != filename:
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


    def delete_user_data(self, user_id: str, storage_dir: Path) -> int:
        """Cancel a user's active jobs and remove their generated local videos."""
        owned = [
            (job_id, job)
            for job_id, job in self._jobs.items()
            if job.user_id == user_id
        ]
        for job_id, job in owned:
            self._jobs.pop(job_id, None)
            if job.task is not None and not job.task.done():
                job.task.cancel()
            self._delete_local_video(job.status.video_url, storage_dir)
        self._persist()
        return len(owned)



_STORE = VideoJobStore()


def get_video_job_store() -> VideoJobStore:
    from app.config.settings import get_settings
    from app.core.paths import resolve_under_project_root

    settings = get_settings()
    _STORE.configure_storage(resolve_under_project_root(settings.video_storage_dir))
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
