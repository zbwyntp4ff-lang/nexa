from __future__ import annotations

import time

import pytest

from app.video_generation.service import VideoJobStore


@pytest.mark.asyncio
async def test_video_file_ownership_survives_store_restart_and_account_wipe(tmp_path):
    storage = tmp_path / "videos"
    storage.mkdir()
    video = storage / "replicate-job_123.mp4"
    video.write_bytes(b"video-bytes" * 20)
    job_id = "a" * 32

    store = VideoJobStore()
    store.record_video_file(job_id, "user-a", str(video), storage)

    restarted_store = VideoJobStore()
    assert await restarted_store.can_access_file(
        video.name, user_id="user-a", enforce=True, storage_dir=storage
    )
    assert not await restarted_store.can_access_file(
        video.name, user_id="user-b", enforce=True, storage_dir=storage
    )
    assert restarted_store.delete_user_data("user-a", storage) == 1
    assert not video.exists()
    assert not (storage / ".ownership.json").exists()


def test_video_file_ttl_cleanup_survives_store_restart(tmp_path):
    storage = tmp_path / "videos"
    storage.mkdir()
    video = storage / "fal-job-123.webm"
    video.write_bytes(b"video-bytes" * 20)
    job_id = "b" * 32

    store = VideoJobStore()
    store.record_video_file(job_id, "user-a", str(video), storage, ttl_seconds=0.01)
    time.sleep(0.03)

    restarted_store = VideoJobStore()
    assert restarted_store.cleanup_expired(storage) == 1
    assert not video.exists()
    assert not (storage / ".ownership.json").exists()
