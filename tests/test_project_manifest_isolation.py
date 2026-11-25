"""Regression tests for strict project manifest tenant isolation."""
from __future__ import annotations

import pytest

from app.agent.project_manifest import ManifestStore, ProjectManifest


def test_authenticated_user_cannot_read_ownerless_local_manifest(tmp_path):
    store = ManifestStore(tmp_path / "projects")
    local = ProjectManifest(user_id=None, goal="private local project")
    store.save(local)

    assert store.get(local.project_id, user_id="user-a") is None
    assert store.get(local.project_id, user_id=None) is not None


def test_user_can_read_only_own_manifest(tmp_path):
    store = ManifestStore(tmp_path / "projects")
    owner_a = ProjectManifest(user_id="user-a", goal="A secret project")
    owner_b = ProjectManifest(user_id="user-b", goal="B secret project")
    store.save(owner_a)
    store.save(owner_b)

    assert store.get(owner_a.project_id, user_id="user-a") is not None
    assert store.get(owner_a.project_id, user_id="user-b") is None
    assert store.get(owner_b.project_id, user_id="user-a") is None


def test_manifest_owner_ids_are_not_silently_normalized(tmp_path):
    store = ManifestStore(tmp_path / "projects")
    with pytest.raises(ValueError):
        store._dir("user/a")
    with pytest.raises(ValueError):
        store._dir("user?a")


def test_invalid_project_id_is_rejected_before_path_lookup(tmp_path):
    store = ManifestStore(tmp_path / "projects")

    assert store.get("../outside", user_id="user-a") is None
    assert store.get("not-a-uuid", user_id="user-a") is None
