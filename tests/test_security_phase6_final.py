"""Final Phase 6 security regressions — ACL, locality, ownership injection."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.tools.desktop.browser_tool import BrowserTool
from app.tools.desktop.locality import clear_locality_cache, is_local_desktop
from app.tools.desktop.open_result import OpenResultTool
from app.tools.desktop.paths import resolve_allowed_path
from app.tools.office.result_store import ResultStore
from app.models.errors import PathTraversalError


@pytest.fixture(autouse=True)
def _clear_locality():
    clear_locality_cache()
    yield
    clear_locality_cache()
    get_settings.cache_clear()


def _save(store: ResultStore, *, user_id: str | None, name: str = "doc.pptx") -> str:
    rec = store.save_bytes(
        b"PK\x03\x04security-fixture",
        filename=name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        extension="pptx",
        task_id="sec",
        tool_name="create_presentation",
        user_id=user_id,
    )
    return rec.file_id


def test_result_store_denies_cross_user_and_orphan_when_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    get_settings.cache_clear()
    store = ResultStore(tmp_path)
    owned = _save(store, user_id="alice")
    orphan = _save(store, user_id=None, name="orphan.pptx")
    assert store.get(owned, user_id="alice") is not None
    assert store.get(owned, user_id="bob") is None
    assert store.get(owned, user_id=None) is None
    assert store.get(orphan, user_id="alice") is None
    # absolute_path must not be treated as an ACL grant
    assert store.absolute_path(owned) is not None
    assert store.get(owned, user_id="bob") is None


def test_result_store_legacy_ownerless_ok_when_enforce_off(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "false")
    get_settings.cache_clear()
    store = ResultStore(tmp_path)
    orphan = _save(store, user_id=None)
    assert store.get(orphan, user_id=None) is not None
    owned = _save(store, user_id="alice", name="a2.pptx")
    assert store.get(owned, user_id="bob") is None  # mismatch still denied


@pytest.mark.asyncio
async def test_open_result_respects_acl_under_enforce(tmp_path, monkeypatch):
    """Regression: open_result must not bypass Results ACL via absolute_path."""
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "1")
    get_settings.cache_clear()
    clear_locality_cache()
    store = ResultStore(tmp_path)
    fid = _save(store, user_id="alice")
    tool = OpenResultTool(tmp_path, store=store)

    denied = await tool.execute(file_id=fid, confirm=True, user_id="bob")
    assert not denied.success
    assert denied.metadata.get("status") == "acl_denied"

    no_user = await tool.execute(file_id=fid, confirm=True)
    assert not no_user.success

    # Owner may pass ACL. Stub OS open so Windows startfile cannot hang the suite.
    import app.tools.desktop.open_result as open_mod

    monkeypatch.setattr(open_mod, "open_with_default_app", lambda _p: True)
    ok_acl = await tool.execute(file_id=fid, confirm=True, user_id="alice")
    assert ok_acl.success
    assert ok_acl.metadata.get("status") == "ok"


@pytest.mark.asyncio
async def test_browser_refused_without_local_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "0")
    clear_locality_cache()
    tool = BrowserTool(tmp_path)
    result = await tool.execute(action="extract", url="https://example.com")
    assert not result.success
    assert result.metadata.get("status") == "remote_refused"


def test_locality_not_enabled_by_dev_environment_alone(monkeypatch):
    monkeypatch.delenv("NEXA_LOCAL_DESKTOP", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("TOKENS_ENFORCE", "false")
    get_settings.cache_clear()
    clear_locality_cache()
    assert is_local_desktop() is False


def test_symlink_escape_blocked(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("leak", encoding="utf-8")
    link = root / "escape"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlink not permitted on this host")
    with pytest.raises(PathTraversalError):
        resolve_allowed_path("escape", roots=[root.resolve()], must_exist=True)


def test_agent_request_model_has_no_client_user_id_field():
    from app.models.agent_api import AgentRunRequest

    fields = set(AgentRunRequest.model_fields)
    assert "user_id" not in fields
    assert "metadata" not in fields


def test_results_http_cross_user_denied(tmp_path, monkeypatch):
    """HTTP Results routes use store ACL under TOKENS_ENFORCE."""
    from app.api.routes import results as results_routes
    from app.main import app

    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "true")
    get_settings.cache_clear()
    store = ResultStore(tmp_path)
    fid = _save(store, user_id="alice-id")

    class FakeUser:
        id = "bob-id"

    monkeypatch.setattr(results_routes, "get_result_store", lambda: store)
    # Bypass auth dep: inject FakeUser via override when enforced
    from app.api.security_deps import require_user_when_enforced

    app.dependency_overrides[require_user_when_enforced] = lambda: FakeUser()
    client = TestClient(app)
    try:
        meta = client.get(f"/api/v1/results/{fid}")
        assert meta.status_code == 404
        dl = client.get(f"/api/v1/results/{fid}/download")
        assert dl.status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_electron_backend_forces_loopback_bind():
    src = Path("frontend/electron/backend.js").read_text(encoding="utf-8")
    assert 'bindHost = allowLan' in src or 'bindHost = "127.0.0.1"' in src or "127.0.0.1" in src
    assert "NEXA_ELECTRON_ALLOW_LAN_BIND" in src
    # Default path must force loopback string
    assert '": "127.0.0.1"' in src or "\"127.0.0.1\"" in src


def test_packaged_devtools_gated():
    src = Path("frontend/electron/main.js").read_text(encoding="utf-8")
    assert "app.isPackaged" in src
    assert "nexa:toggle-devtools" in src
