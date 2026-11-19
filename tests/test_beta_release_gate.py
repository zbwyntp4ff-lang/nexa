"""Beta release gate — production guards + Build ACL under TOKENS_ENFORCE."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.build.models import BuildProjectRecord
from app.build import store
from app.config.production_guards import (
    ProductionConfigError,
    assert_durable_production,
    validate_production_settings,
)
from app.config.settings import Settings, get_settings


def _durable_cloud_env(monkeypatch, **extra: str) -> Settings:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NEXA_STORAGE_MODE", "persistent")
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("WORKFLOWS_ENABLED", "false")
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "false")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("MEMORY_BACKEND", "sql")
    monkeypatch.setenv("AUTH_PUBLIC_BASE_URL", "https://nexa.example.com")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://nexa.example.com")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "noreply@nexa.example.com")
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return Settings(_env_file=None)


def test_durable_production_rejects_local_desktop_and_mock(monkeypatch):
    settings = _durable_cloud_env(
        monkeypatch,
        NEXA_LOCAL_DESKTOP="1",
        NEXA_ELECTRON_ALLOW_LAN_BIND="0",
        AI_PROVIDER="mock",
    )
    problems = validate_production_settings(settings)
    assert any("NEXA_LOCAL_DESKTOP" in p for p in problems)
    assert any("mock" in p.lower() for p in problems)
    with pytest.raises(ProductionConfigError):
        assert_durable_production(settings)


def test_durable_production_rejects_lan_bind_and_devtools(monkeypatch):
    settings = _durable_cloud_env(
        monkeypatch,
        NEXA_LOCAL_DESKTOP="0",
        NEXA_ELECTRON_ALLOW_LAN_BIND="1",
        NEXA_ALLOW_PACKAGED_DEVTOOLS="1",
        AI_PROVIDER="openrouter",
    )
    problems = validate_production_settings(settings)
    assert any("LAN_BIND" in p for p in problems)
    assert any("DEVTOOLS" in p for p in problems)

def test_build_export_preview_denied_cross_user(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()

    root = tmp_path / "builds" / "p1"
    root.mkdir(parents=True)
    (root / "index.html").write_text("<html>secret</html>", encoding="utf-8")

    # Point build store at temp by monkeypatching workspace + upsert into store file
    from app.build import store as build_store
    from app.core.paths import resolve_under_project_root

    monkeypatch.setenv("NEXA_PROJECT_ROOT", str(tmp_path))
    # Use upsert with owned record
    rec = BuildProjectRecord(
        project_id="proj-alice",
        slug="alice-slug",
        title="Alice",
        user_id="alice",
        root_rel="builds/p1",
        entry_file="index.html",
        files=["index.html"],
        preview_url="/api/v1/build/preview/proj-alice/index.html",
    )
    # Ensure workspace_root resolves under tmp
    monkeypatch.setattr(build_store, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        build_store,
        "get_project",
        lambda pid: rec if pid == "proj-alice" else None,
    )

    from app.api.security_deps import require_user_when_enforced
    from app.main import app

    class Bob:
        id = "bob"

    app.dependency_overrides[require_user_when_enforced] = lambda: Bob()
    client = TestClient(app)
    try:
        exp = client.get("/api/v1/build/export/proj-alice")
        assert exp.status_code == 404
        assert b"secret" not in exp.content
        prev = client.get("/api/v1/build/preview/proj-alice/index.html")
        assert prev.status_code == 404
        assert b"secret" not in prev.content
        meta = client.get("/api/v1/build/projects/proj-alice")
        assert meta.status_code == 404
        listing = client.get("/api/v1/build/projects")
        assert listing.status_code == 200
        assert listing.json()["count"] == 0
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_build_export_owner_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    get_settings.cache_clear()
    (tmp_path / "builds" / "p1").mkdir(parents=True)
    (tmp_path / "builds" / "p1" / "index.html").write_text("<html>ok</html>", encoding="utf-8")

    from app.build import store as build_store

    rec = BuildProjectRecord(
        project_id="proj-alice",
        slug="alice-slug",
        title="Alice",
        user_id="alice",
        root_rel="builds/p1",
        entry_file="index.html",
        files=["index.html"],
    )
    monkeypatch.setattr(build_store, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(
        build_store,
        "get_project",
        lambda pid: rec if pid == "proj-alice" else None,
    )

    from app.api.security_deps import require_user_when_enforced
    from app.main import app

    class Alice:
        id = "alice"

    app.dependency_overrides[require_user_when_enforced] = lambda: Alice()
    client = TestClient(app)
    try:
        exp = client.get("/api/v1/build/export/proj-alice")
        assert exp.status_code == 200
        assert exp.headers.get("content-type", "").startswith("application/zip")
        assert len(exp.content) > 20
        prev = client.get("/api/v1/build/preview/proj-alice/index.html")
        assert prev.status_code == 200
        assert b"ok" in prev.content
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_journal_global_dump_blocked_under_enforce(monkeypatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    get_settings.cache_clear()
    from app.api.security_deps import require_user_when_enforced
    from app.main import app

    class U:
        id = "u1"

    app.dependency_overrides[require_user_when_enforced] = lambda: U()
    client = TestClient(app)
    try:
        r = client.get("/api/v1/journal")
        assert r.status_code == 200
        assert r.json()["events"] == []
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
