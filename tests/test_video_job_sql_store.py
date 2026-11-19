from __future__ import annotations

import pytest

from app.db.engine import Database
from app.video_generation.models import VideoJobStatus
from app.video_generation.service import VideoJobStore


@pytest.mark.asyncio
async def test_video_job_status_survives_store_restart(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'nexa.db'}")
    store = VideoJobStore(db)
    status = VideoJobStatus(
        job_id="a" * 32,
        phase="queued",
        progress=1,
        message="Queued",
    )
    await store.create(status.job_id, status, user_id="user-a")
    await store.update(status.job_id, phase="ready", progress=100, message="Ready", video_url="https://example.test/video.mp4")

    restarted = VideoJobStore(db)
    loaded = await restarted.get(status.job_id, user_id="user-a", enforce=True)
    assert loaded is not None
    assert loaded.phase == "ready"
    assert loaded.progress == 100
    assert loaded.video_url == "https://example.test/video.mp4"
    assert await restarted.get(status.job_id, user_id="user-b", enforce=True) is None


@pytest.mark.asyncio
async def test_interrupted_video_job_is_marked_failed_after_restart(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'nexa.db'}")
    store = VideoJobStore(db)
    status = VideoJobStatus(job_id="b" * 32, phase="generating", progress=55)
    await store.create(status.job_id, status, user_id="user-a")

    restarted = VideoJobStore(db)
    loaded = await restarted.get(status.job_id, user_id="user-a", enforce=True)
    assert loaded is not None
    assert loaded.phase == "failed"
    assert loaded.progress == 100
    assert "restart" in loaded.message.lower()
