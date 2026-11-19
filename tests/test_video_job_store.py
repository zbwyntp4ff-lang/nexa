"""Restart and ownership tests for the durable video job manifest."""
from __future__ import annotations

import asyncio

import pytest

from app.video_generation.models import VideoJobStatus
from app.video_generation.service import VideoJobStore


@pytest.mark.asyncio
async def test_video_job_owner_and_ready_status_survive_restart(tmp_path):
    video = tmp_path / "owned.mp4"
    video.write_bytes(b"video")
    store = VideoJobStore(tmp_path)
    status = VideoJobStatus(
        job_id="job-owned",
        phase="ready",
        progress=100,
        message="Video ready",
        video_url="/api/v1/video/files/owned.mp4",
        provider="test-provider",
        model="test-model",
    )
    await store.create(status.job_id, status, user_id="user-a")

    restarted = VideoJobStore(tmp_path)
    restored = await restarted.get(status.job_id, user_id="user-a", enforce=True)
    assert restored is not None
    assert restored.phase == "ready"
    assert restored.video_url == status.video_url
    assert await restarted.get(status.job_id, user_id="user-b", enforce=True) is None
    assert await restarted.can_access_file("owned.mp4", user_id="user-a", enforce=True)
    assert not await restarted.can_access_file("owned.mp4", user_id="user-b", enforce=True)


@pytest.mark.asyncio
async def test_in_progress_video_job_is_marked_interrupted_after_restart(tmp_path):
    store = VideoJobStore(tmp_path)
    status = VideoJobStatus(
        job_id="job-running",
        phase="generating",
        progress=45,
        message="Generating",
    )
    await store.create(status.job_id, status, user_id="user-a")

    restarted = VideoJobStore(tmp_path)
    restored = await restarted.get(status.job_id, user_id="user-a", enforce=True)
    assert restored is not None
    assert restored.phase == "failed"
    assert "restarted" in restored.message.lower()
    assert restored.error is None


def test_video_account_deletion_removes_owned_file_and_manifest_entry(tmp_path):
    video = tmp_path / "private.mp4"
    video.write_bytes(b"private video")
    store = VideoJobStore(tmp_path)
    status = VideoJobStatus(
        job_id="job-private",
        phase="ready",
        progress=100,
        video_url="/api/v1/video/files/private.mp4",
    )
    asyncio.run(store.create(status.job_id, status, user_id="user-a"))

    assert store.delete_user_data("user-a", tmp_path) == 1
    assert not video.exists()

    restarted = VideoJobStore(tmp_path)
    assert asyncio.run(restarted.get(status.job_id, user_id="user-a", enforce=True)) is None


def test_corrupt_video_manifest_fails_closed(tmp_path):
    (tmp_path / ".nexa_video_jobs.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        VideoJobStore(tmp_path)

@pytest.mark.asyncio
async def test_manifest_does_not_persist_motion_prompts_or_signed_provider_urls(tmp_path):
    store = VideoJobStore(tmp_path)
    status = VideoJobStatus(
        job_id="job-remote",
        phase="ready",
        progress=100,
        message="contains private provider details",
        video_url="https://provider.example/video.mp4?signature=secret-token",
        motion_plan={
            "scene_summary": "private image description",
            "motion_prompt": "private user prompt",
            "conservative": True,
            "source": "user",
        },
    )
    await store.create(status.job_id, status, user_id="user-a")

    manifest = (tmp_path / ".nexa_video_jobs.json").read_text(encoding="utf-8")
    assert "secret-token" not in manifest
    assert "private user prompt" not in manifest
    assert "private image description" not in manifest
    assert "private provider details" not in manifest

    restarted = VideoJobStore(tmp_path)
    restored = await restarted.get(status.job_id, user_id="user-a", enforce=True)
    assert restored is not None
    assert restored.phase == "failed"
    assert restored.video_url is None

def test_video_account_deletion_never_unlinks_remote_url_basename(tmp_path):
    remote_named_file = tmp_path / "same-name.mp4"
    remote_named_file.write_bytes(b"belongs to another local job")
    store = VideoJobStore()
    status = VideoJobStatus(
        job_id="job-remote",
        phase="ready",
        progress=100,
        video_url="https://provider.example/api/v1/video/files/same-name.mp4?sig=secret",
    )
    asyncio.run(store.create(status.job_id, status, user_id="user-a"))

    assert store.delete_user_data("user-a", tmp_path) == 1
    assert remote_named_file.exists()

def test_video_store_startup_removes_orphaned_generated_files(tmp_path):
    orphan = tmp_path / "orphaned.mp4"
    orphan.write_bytes(b"orphan")
    VideoJobStore(tmp_path)
    assert not orphan.exists()

