"""In-memory image-to-video job tracker + orchestration."""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from app.attachments.manager import AttachmentManager
from app.billing.entitlements import EntitlementService
from app.billing.errors import EntitlementDeniedError
from app.config.settings import Settings
from app.core.paths import resolve_under_project_root
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
        self._manifest_lock = threading.RLock()

    def _manifest_path(self, storage_dir: Path) -> Path:
        root = storage_dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root / ".ownership.json"

    def _read_manifest(self, storage_dir: Path) -> dict[str, dict]:
        path = self._manifest_path(storage_dir)
        with self._manifest_lock:
            if not path.exists():
                return {}
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError("Video ownership manifest is unreadable; refusing unsafe cleanup.") from exc
            if not isinstance(raw, dict):
                raise RuntimeError("Video ownership manifest has an invalid format.")
            return {key: value for key, value in raw.items() if isinstance(key, str) and isinstance(value, dict)}

    def _write_manifest(self, storage_dir: Path, manifest: dict[str, dict]) -> None:
        path = self._manifest_path(storage_dir)
        with self._manifest_lock:
            if not manifest:
                path.unlink(missing_ok=True)
                return
            fd, temp_name = tempfile.mkstemp(prefix=".ownership-", dir=storage_dir)
            try:
                try:
                    os.fchmod(fd, 0o600)
                except (AttributeError, OSError):
                    pass
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(manifest, stream, ensure_ascii=False, separators=(",", ":"))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_name, path)
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)

    def _safe_video_path(self, storage_dir: Path, job_id: str, entry: dict) -> Path | None:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            return None
        filename = entry.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}\.(?:mp4|webm|mov)", filename, re.IGNORECASE):
            return None
        candidate = storage_dir / filename
        if candidate.is_symlink():
            return candidate
        try:
            if candidate.resolve().parent != storage_dir.resolve():
                return None
        except OSError:
            return None
        return candidate

    def record_video_file(
        self, job_id: str, user_id: str | None, local_path: str | None, storage_dir: Path,
        *, ttl_seconds: float = 7 * 24 * 60 * 60,
    ) -> None:
        if not user_id or not local_path:
            return
        root = storage_dir.resolve()
        candidate = Path(local_path)
        if candidate.is_symlink() or not candidate.is_file():
            return
        resolved = candidate.resolve()
        if resolved.parent != root:
            return
        manifest = self._read_manifest(root)
        manifest[job_id] = {
            "user_id": user_id,
            "filename": resolved.name,
            "expires_at": time.time() + ttl_seconds,
        }
        self._write_manifest(root, manifest)

    def cleanup_expired(self, storage_dir: Path) -> int:
        manifest = self._read_manifest(storage_dir)
        now = time.time()
        removed = 0
        for job_id, entry in list(manifest.items()):
            try:
                expired = float(entry["expires_at"]) < now
            except (KeyError, TypeError, ValueError):
                continue
            if not expired:
                continue
            candidate = self._safe_video_path(storage_dir, job_id, entry)
            if candidate:
                candidate.unlink(missing_ok=True)
            manifest.pop(job_id, None)
            removed += 1
        if removed:
            self._write_manifest(storage_dir, manifest)
        return removed

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

    async def can_access_file(
        self, filename: str, *, user_id: str | None = None, enforce: bool = False,
        storage_dir: Path | None = None,
    ) -> bool:
        """Allow access only when a live job or durable manifest assigns the file to the caller."""
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
        if not storage_dir or not user_id:
            return False
        manifest = self._read_manifest(storage_dir)
        for job_id, entry in manifest.items():
            if entry.get("filename") != filename:
                continue
            if enforce and entry.get("user_id") != user_id:
                return False
            return entry.get("user_id") == user_id
        return False

    async def attach_task(self, job_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].task = task


    def delete_user_data(self, user_id: str, storage_dir: Path) -> int:
        """Cancel live jobs and remove all manifest-tracked videos owned by the user."""
        root = storage_dir.resolve()
        manifest = self._read_manifest(root)
        persisted_ids = {
            job_id for job_id, entry in manifest.items()
            if entry.get("user_id") == user_id
        }
        for job_id in persisted_ids:
            entry = manifest.pop(job_id, {})
            candidate = self._safe_video_path(root, job_id, entry)
            if candidate:
                candidate.unlink(missing_ok=True)
        if persisted_ids:
            self._write_manifest(root, manifest)

        owned = [(job_id, job) for job_id, job in self._jobs.items() if job.user_id == user_id]
        for job_id, job in owned:
            self._jobs.pop(job_id, None)
            if job.task is not None and not job.task.done():
                job.task.cancel()
            video_url = job.status.video_url or ""
            filename = Path(urlparse(video_url).path).name
            if filename and re.fullmatch(r"[A-Za-z0-9_-]{1,64}\.(?:mp4|webm|mov)", filename, re.IGNORECASE):
                candidate = root / filename
                if candidate.is_symlink():
                    candidate.unlink(missing_ok=True)
                elif candidate.resolve().parent == root and candidate.is_file():
                    candidate.unlink(missing_ok=True)
        return len(persisted_ids | {job_id for job_id, _ in owned})


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
            self._store.record_video_file(
                job_id, user_id, result.local_path, Path(resolve_under_project_root(self._settings.video_storage_dir))
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
