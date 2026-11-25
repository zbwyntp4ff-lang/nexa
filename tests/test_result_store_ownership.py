"""Regression tests for exact ownership of generated result files."""
from __future__ import annotations

from app.tools.office.result_store import ResultStore


def _save(store: ResultStore, *, user_id: str | None):
    return store.save_bytes(
        b"private generated content",
        filename="report",
        media_type="application/pdf",
        extension="pdf",
        task_id="task-1",
        user_id=user_id,
    )


def test_ownerless_legacy_result_is_local_only(tmp_path):
    store = ResultStore(tmp_path)
    record = _save(store, user_id=None)

    # The local unauthenticated desktop namespace retains its legacy access.
    assert store.get(record.file_id, user_id=None) is not None

    # An authenticated account must never inherit access to the shared namespace.
    assert store.get(record.file_id, user_id="user-a") is None
    assert store.get(record.file_id, user_id="user-b") is None


def test_owned_result_is_visible_only_to_exact_owner(tmp_path):
    store = ResultStore(tmp_path)
    record = _save(store, user_id="user-a")

    assert store.get(record.file_id, user_id="user-a") is not None
    assert store.get(record.file_id, user_id="user-b") is None
    assert store.get(record.file_id, user_id=None) is None


def test_different_users_cannot_read_each_others_results(tmp_path):
    store = ResultStore(tmp_path)
    a = _save(store, user_id="user-a")
    b = _save(store, user_id="user-b")

    assert store.get(a.file_id, user_id="user-b") is None
    assert store.get(b.file_id, user_id="user-a") is None
