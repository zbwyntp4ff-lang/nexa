from __future__ import annotations

import pytest

from app.models.errors import AttachmentNotFoundError

from app.attachments.manager import AttachmentManager
from app.attachments.sql_store import SqlAttachmentStore
from app.db.engine import Database
from app.documents.processor import build_default_document_processor


def _manager(tmp_path, db: Database) -> AttachmentManager:
    return AttachmentManager(
        storage_dir=tmp_path / "attachments",
        document_processor=build_default_document_processor(
            max_size_bytes=1_000_000,
            max_pages=20,
            max_text_chars=100_000,
        ),
        max_size_bytes=1_000_000,
        max_attachments_per_message=5,
        processing_timeout_seconds=5,
        max_concurrent_jobs=2,
        ttl_seconds=3600,
        context_max_chars=6000,
        store=SqlAttachmentStore(db),
    )


@pytest.mark.asyncio
async def test_document_metadata_and_text_survive_manager_restart(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'nexa.db'}")
    first = _manager(tmp_path, db)
    record = await first.upload("notes.txt", b"Durable NEXA attachment content.", user_id="user-a")

    restarted = _manager(tmp_path, db)
    loaded = restarted.get(record.id, user_id="user-a")
    assert loaded.id == record.id
    assert loaded.status.value == "ready"
    assert restarted.get_text(record.id, user_id="user-a") == "Durable NEXA attachment content."
    assert restarted.list(user_id="user-a")[0].id == record.id
    assert restarted.document_context([record.id], "durable attachment", user_id="user-a")
    with pytest.raises(AttachmentNotFoundError):
        restarted.get(record.id, user_id="user-b")


@pytest.mark.asyncio
async def test_account_wipe_removes_sql_attachment_content(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'nexa.db'}")
    manager = _manager(tmp_path, db)
    record = await manager.upload("private.txt", b"private document text", user_id="user-a")
    await manager.upload("other.txt", b"other user's text", user_id="user-b")

    assert manager.delete_user("user-a") == 1
    restarted = _manager(tmp_path, db)
    assert restarted.list(user_id="user-a") == []
    with pytest.raises(AttachmentNotFoundError):
        restarted.get(record.id, user_id="user-a")
    assert len(restarted.list(user_id="user-b")) == 1
