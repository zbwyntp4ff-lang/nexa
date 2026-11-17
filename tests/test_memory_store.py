"""Persistence safety tests for the legacy JSON memory backend."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.memory.models import MemoryItem, MemoryType
from app.memory.store import LocalMemoryStore


def test_missing_memory_store_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    store = LocalMemoryStore(path)
    assert store.search() == []
    assert not path.exists()


def test_valid_memory_store_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    store = LocalMemoryStore(path)
    item = MemoryItem(type=MemoryType.LONG_TERM, content="Keep this memory", user_id="u1")
    store.save(item)

    reopened = LocalMemoryStore(path)
    loaded = reopened.get(item.id)
    assert loaded is not None
    assert loaded.content == "Keep this memory"
    assert loaded.user_id == "u1"


def test_corrupt_memory_store_fails_closed_without_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    original = "{ this is not valid JSON"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(RuntimeError, match="Cannot load NEXA memory store"):
        LocalMemoryStore(path)

    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("payload", [
    "[]",
    "{}",
    json.dumps({"items": "not-a-list"}),
    json.dumps({"items": [{"id": "broken", "type": "unknown"}]}),
])
def test_invalid_memory_store_schema_fails_closed(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "memory.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(RuntimeError, match="Cannot load NEXA memory store"):
        LocalMemoryStore(path)

    assert path.read_text(encoding="utf-8") == payload
