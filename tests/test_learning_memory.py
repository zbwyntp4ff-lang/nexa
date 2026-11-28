"""Learning & Memory — isolated unit/integration tests (mocked stores, no paid APIs).

Real integrations covered elsewhere: document parsers (test_documents), provider
catalog (test_cloud_providers). This file does **not** claim fine-tuning works.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.knowledge_core.feedback import FeedbackEvent, record_feedback, recent_feedback
from app.learning.contradictions import find_contradictions
from app.learning.eval import compute_feedback_stats, run_eval_snapshot
from app.learning.improve import propose_from_feedback, set_proposal_status
from app.learning.memory_context import build_memory_hint
from app.learning.settings import LearningSettings, get_learning_settings, save_learning_settings
from app.memory.manager import MemoryManager
from app.memory.models import MemoryType
from app.memory.store import InMemoryStore
from app.models.errors import SecretInMemoryError


@pytest.fixture
def memory() -> MemoryManager:
    return MemoryManager(InMemoryStore(), default_search_limit=50)


@pytest.fixture
def learning_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_path = tmp_path / "learning_settings.json"
    feedback_path = tmp_path / "feedback.jsonl"
    proposals_path = tmp_path / "proposals.json"
    monkeypatch.setattr("app.learning.settings._PATH", settings_path)
    monkeypatch.setattr("app.knowledge_core.feedback._FEEDBACK_PATH", feedback_path)
    monkeypatch.setattr("app.learning.improve._PATH", proposals_path)
    return settings_path


def test_memory_save_and_retrieve(memory: MemoryManager):
    memory.save("User prefers concise answers", type=MemoryType.USER_PREFERENCE, user_id="u1")
    memory.save("Project codename is Orion", type=MemoryType.LONG_TERM, user_id="u1")
    hits = memory.search("Orion", user_id="u1")
    assert any("Orion" in h.item.content for h in hits)


def test_memory_user_isolation(memory: MemoryManager):
    memory.save("Alice secret fact", type=MemoryType.LONG_TERM, user_id="alice")
    memory.save("Bob secret fact", type=MemoryType.LONG_TERM, user_id="bob")
    alice = memory.search("secret", user_id="alice")
    bob = memory.search("secret", user_id="bob")
    assert all(h.item.user_id == "alice" for h in alice)
    assert all(h.item.user_id == "bob" for h in bob)
    assert not any("Bob" in h.item.content for h in alice)


def test_memory_delete_scoped(memory: MemoryManager):
    a = memory.save("keep me", type=MemoryType.LONG_TERM, user_id="u1")
    b = memory.save("delete me", type=MemoryType.LONG_TERM, user_id="u1")
    assert memory.delete(b.id, user_id="u1") is True
    with pytest.raises(Exception):
        memory.delete(a.id, user_id="u2")
    assert memory.get(a.id).content == "keep me"


def test_memory_clear_is_scoped_to_one_user(memory: MemoryManager):
    memory.save("Alice memory", type=MemoryType.LONG_TERM, user_id="alice")
    memory.save("Bob memory", type=MemoryType.LONG_TERM, user_id="bob")
    assert memory.clear(user_id="alice") == 1
    assert memory.search(query="", user_id="alice") == []
    assert any(item.item.content == "Bob memory" for item in memory.search(query="", user_id="bob"))


def test_memory_rejects_secrets(memory: MemoryManager):
    with pytest.raises(SecretInMemoryError):
        memory.save("sk-abcdefghijklmnopqrstuvwxyz012345", type=MemoryType.LONG_TERM, user_id="u1")


def test_memory_hint_only_long_term_and_prefs(memory: MemoryManager):
    memory.save("noise conversation", type=MemoryType.CONVERSATION, user_id="u1")
    memory.save("Likes dark mode", type=MemoryType.USER_PREFERENCE, user_id="u1")
    hint = build_memory_hint(memory, user_id="u1", query="theme", enabled=True)
    assert hint is not None
    assert "dark mode" in hint
    assert "noise conversation" not in hint
    assert build_memory_hint(memory, user_id="u1", query="x", enabled=False) is None


def test_contradiction_detection(memory: MemoryManager):
    memory.save("Alice likes coffee every morning", type=MemoryType.LONG_TERM, user_id="u1")
    hits = find_contradictions(
        memory,
        user_id="u1",
        content="Alice does not like coffee every morning",
        type=MemoryType.LONG_TERM,
    )
    assert hits
    assert hits[0].existing_id


def test_feedback_not_auto_fact(learning_tmp: Path):
    record_feedback(
        FeedbackEvent(
            rating="incorrect",
            user_request="What is 2+2?",
            nexa_response="5",
            note="should be 4",
        )
    )
    events = recent_feedback(10)
    assert len(events) == 1
    assert events[0].rating == "incorrect"
    # Feedback alone must not rewrite learning settings into "truth".
    settings = get_learning_settings()
    assert settings.last_eval_summary is None or "fine-tune" not in (settings.last_eval_summary or "").lower()


def test_eval_snapshot_and_proposals(learning_tmp: Path):
    for i in range(4):
        record_feedback(
            FeedbackEvent(
                rating="incorrect" if i < 3 else "useful",
                user_request=f"q{i}",
                nexa_response=f"a{i}",
                note="wrong citation" if i < 2 else None,
            )
        )
    stats = compute_feedback_stats()
    assert stats.total == 4
    assert stats.positive_ratio is not None
    snap = run_eval_snapshot()
    assert "samples" in snap.summary.lower() or "feedback" in snap.summary.lower()
    created = propose_from_feedback()
    assert created
    applied = set_proposal_status(created[0].id, "applied")
    assert applied is not None
    assert applied.after_summary is not None
    # Applying records measurement — does not claim model weights changed.
    assert applied.status == "applied"


def test_learning_settings_persist(learning_tmp: Path):
    saved = save_learning_settings(
        LearningSettings(memory_enabled=False, feedback_enabled=False, auto_knowledge_base=False)
    )
    assert saved.memory_enabled is False
    loaded = get_learning_settings()
    assert loaded.feedback_enabled is False
    assert learning_tmp.exists()
    raw = json.loads(learning_tmp.read_text(encoding="utf-8"))
    assert raw["memory_enabled"] is False


def test_no_silent_mock_in_learning_status_note():
    """Fine-tuning must be explicitly unavailable — not a hidden mock trainer."""
    note = LearningSettings().model_dump()
    assert "memory_enabled" in note
    # Product honesty is asserted via LearningStatusResponse.fine_tuning in the API.
    from app.api.routes.learning import LearningStatusResponse

    sample = LearningStatusResponse(
        settings=LearningSettings(),
        memory_enabled=True,
        memory_item_count=0,
        knowledge_document_count=0,
        knowledge_chunk_hint="x",
        feedback_stats=compute_feedback_stats(),
        last_index_at=None,
        last_eval_at=None,
        last_eval_summary=None,
    )
    assert sample.fine_tuning["available_in_product"] is False
    assert sample.fine_tuning["categories"]["parameter_update"] == "not_enabled"


def test_authenticated_user_cannot_update_or_delete_ownerless_legacy_memory(memory: MemoryManager):
    from app.models.errors import MemoryItemNotFoundError

    legacy = memory.save("Legacy local memory", type=MemoryType.LONG_TERM)
    with pytest.raises(MemoryItemNotFoundError):
        memory.update(legacy.id, content="overwritten by account", user_id="alice")
    with pytest.raises(MemoryItemNotFoundError):
        memory.delete(legacy.id, user_id="alice")
    assert memory.get(legacy.id).content == "Legacy local memory"


def test_ownerless_memory_remains_manageable_in_local_namespace(memory: MemoryManager):
    legacy = memory.save("Legacy local memory", type=MemoryType.LONG_TERM)
    updated = memory.update(legacy.id, content="Updated locally")
    assert updated.content == "Updated locally"
    assert memory.delete(legacy.id) is True
