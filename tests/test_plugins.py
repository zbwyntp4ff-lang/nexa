"""Part 14 — Plugin Hub manager, security, adapters."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.secrets import redact_secrets
from app.main import app
from app.models.errors import PathTraversalError, SSRFProtectionError
from app.plugins.adapters.playwright_adapter import PlaywrightAdapter
from app.plugins.base import PluginContext
from app.plugins.crypto import decrypt_secret, encrypt_secret
from app.plugins.errors import (
    PluginConfirmationRequiredError,
    PluginNotConnectedError,
    PluginPermissionDeniedError,
)
from app.plugins.manager import PluginManager, get_plugin_manager
from app.plugins.store import PluginStore
from app.tools.registry import ToolRegistry, get_default_tool_registry


def _manager(tmp_path: Path) -> PluginManager:
    registry = ToolRegistry()
    return PluginManager(
        store=PluginStore(tmp_path / "store.json"),
        workspace_root=tmp_path / "ws",
        master_key=b"k" * 32,
        registry=registry,
        timeout_seconds=8.0,
    )


@pytest.fixture()
def mgr(tmp_path: Path) -> PluginManager:
    return _manager(tmp_path)


def test_catalog_has_five_plugins(mgr: PluginManager):
    cards = mgr.list_public()
    ids = {c["id"] for c in cards}
    assert ids == {"vscode", "github", "playwright", "blender", "godot"}
    racing = mgr.list_public(query="github")
    assert [c["id"] for c in racing] == ["github"]
    assert mgr.list_public(category="editor")[0]["id"] == "vscode"


@pytest.mark.asyncio
async def test_vscode_connect_disconnect_and_tools(mgr: PluginManager):
    card = await mgr.connect("vscode", permissions=["files.read", "files.write"])
    assert card["enabled"] is True
    assert card["status"] in {"connected", "connected_limited"}
    names = {t.name for t in mgr._registry.list()}  # noqa: SLF001
    assert "plugin_vscode" in names

    listed = await mgr.invoke("vscode", "list", {})
    assert listed.success
    preview = await mgr.invoke(
        "vscode", "preview_write", {"path": "hello.txt", "content": "hi\n"}
    )
    assert "hello.txt" in preview.output["diff"] or preview.output["diff"] == "(no changes)"
    with pytest.raises(PluginConfirmationRequiredError):
        await mgr.invoke("vscode", "apply_write", {"path": "hello.txt", "content": "hi\n"})
    applied = await mgr.invoke(
        "vscode",
        "apply_write",
        {"path": "hello.txt", "content": "hi\n"},
        confirm=True,
    )
    assert applied.success
    undone = await mgr.invoke("vscode", "undo", {}, confirm=True)
    assert undone.success

    await mgr.disconnect("vscode")
    names2 = {t.name for t in mgr._registry.list()}  # noqa: SLF001
    assert "plugin_vscode" not in names2
    with pytest.raises(PluginNotConnectedError):
        await mgr.invoke("vscode", "list", {})


@pytest.mark.asyncio
async def test_permissions_deny_by_default(mgr: PluginManager):
    await mgr.connect("vscode", permissions=["files.read"])
    with pytest.raises(PluginPermissionDeniedError):
        await mgr.invoke(
            "vscode", "preview_write", {"path": "a.txt", "content": "x"}, confirm=False
        )


@pytest.mark.asyncio
async def test_path_traversal_blocked(mgr: PluginManager):
    await mgr.connect("vscode", permissions=["files.read", "files.write"])
    with pytest.raises(PathTraversalError):
        await mgr.invoke("vscode", "read", {"path": "../secret.txt"})


@pytest.mark.asyncio
async def test_github_needs_token(mgr: PluginManager):
    card = await mgr.connect("github", permissions=["github.read"])
    assert card["enabled"] is False
    assert card["status"] == "needs_token"
    assert card["has_token"] is False


@pytest.mark.asyncio
async def test_github_token_not_stored_plaintext(mgr: PluginManager, tmp_path: Path, monkeypatch):
    async def fake_get(self, ctx, path):  # noqa: ANN001
        return {"login": "octocat", "id": 1}

    monkeypatch.setattr("app.plugins.adapters.github.GitHubAdapter._get", fake_get)
    token = "ghp_" + ("a" * 36)
    card = await mgr.connect(
        "github",
        permissions=["github.read"],
        secrets={"token": token},
    )
    assert card["enabled"] is True
    assert card["has_token"] is True
    dumped = (tmp_path / "store.json").read_text(encoding="utf-8")
    assert token not in dumped
    assert "ghp_" not in dumped
    who = await mgr.invoke("github", "whoami", {})
    assert who.output["login"] == "octocat"


@pytest.mark.asyncio
async def test_github_create_issue_requires_confirm_and_write(mgr: PluginManager, monkeypatch):
    async def fake_get(self, ctx, path):  # noqa: ANN001
        return {"login": "octocat", "id": 1}

    monkeypatch.setattr("app.plugins.adapters.github.GitHubAdapter._get", fake_get)
    await mgr.connect("github", permissions=["github.read"], secrets={"token": "ghp_" + ("b" * 36)})
    with pytest.raises(PluginPermissionDeniedError):
        await mgr.invoke(
            "github",
            "create_issue",
            {"owner": "o", "repo": "r", "title": "x"},
            confirm=True,
        )


def test_secret_redaction():
    text = "token ghp_" + ("c" * 36)
    assert "ghp_" not in redact_secrets(text)
    fine = "github_pat_" + ("d" * 22)
    assert "github_pat_" not in redact_secrets(fine)


def test_crypto_roundtrip():
    key = b"z" * 32
    blob = encrypt_secret("super-secret", key)
    assert "super-secret" not in blob
    assert decrypt_secret(blob, key) == "super-secret"


@pytest.mark.asyncio
async def test_playwright_ssrf_blocked():
    adapter = PlaywrightAdapter()
    ctx = PluginContext(
        workspace_root=Path("."),
        granted_permissions=frozenset({"browser.navigate"}),
    )
    with pytest.raises(SSRFProtectionError):
        await adapter.execute("open", {"url": "http://127.0.0.1/"}, ctx)
    with pytest.raises(SSRFProtectionError):
        await adapter.execute("open", {"url": "file:///etc/passwd"}, ctx)


@pytest.mark.asyncio
async def test_playwright_click_requires_confirm():
    adapter = PlaywrightAdapter()
    ctx = PluginContext(
        workspace_root=Path("."),
        granted_permissions=frozenset({"browser.navigate", "browser.interact", "browser.submit"}),
        confirm=False,
    )
    with pytest.raises(PluginConfirmationRequiredError):
        await adapter.execute("click", {"url": "https://example.com", "selector": "#buy-now"}, ctx)


def test_api_plugins_require_auth(tmp_path: Path):
    get_plugin_manager.cache_clear()
    get_default_tool_registry.cache_clear()
    client = TestClient(app)
    listed = client.get("/api/v1/plugins")
    assert listed.status_code == 401
    conn = client.post("/api/v1/plugins/vscode/connect", json={"permissions": ["files.read"]})
    assert conn.status_code == 401
    get_plugin_manager.cache_clear()


@pytest.mark.asyncio
async def test_user_plugin_connections_are_not_registered_globally_or_shared(mgr: PluginManager):
    alice = await mgr.connect(
        "vscode", user_id="alice", permissions=["files.read", "files.write"]
    )
    assert alice["enabled"] is True
    assert "plugin_vscode" not in {tool.name for tool in mgr._registry.list()}
    mgr.restore_connected_tools()
    assert "plugin_vscode" not in {tool.name for tool in mgr._registry.list()}

    bob = await mgr.connect(
        "vscode", user_id="bob", permissions=["files.read", "files.write"]
    )
    assert bob["enabled"] is True

    alice_ctx = mgr._context(mgr.adapter("vscode"), mgr._store.get("vscode", user_id="alice"))
    bob_ctx = mgr._context(mgr.adapter("vscode"), mgr._store.get("vscode", user_id="bob"))
    assert alice_ctx.workspace_root != bob_ctx.workspace_root

    await mgr.disconnect("vscode", user_id="alice")
    assert mgr._store.get("vscode", user_id="bob").enabled is True
    assert "plugin_vscode" not in {tool.name for tool in mgr._registry.list()}


def test_plugin_audit_and_workspace_deletion_are_user_scoped(mgr: PluginManager, tmp_path: Path):
    import hashlib

    mgr._audit.record(plugin_id="vscode", action="read", status="ok", user_id="alice")
    mgr._audit.record(plugin_id="vscode", action="read", status="ok", user_id="bob")
    alice_events = mgr.audit("vscode", user_id="alice")
    assert len(alice_events) == 1
    assert alice_events[0]["user_id"] == "alice"

    alice_root = mgr._workspace_root / hashlib.sha256(b"alice").hexdigest()
    alice_root.mkdir(parents=True)
    (alice_root / "private.txt").write_text("alice data", encoding="utf-8")
    assert mgr.delete_user_data("alice") == 0
    assert not alice_root.exists()

def test_crypto_reads_legacy_nexa1_secret():
    from app.plugins.crypto import decrypt_secret

    legacy = "TkVYQTEAAQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eH_DR8vu56kFpusuPJjcPTz2afbBKIxKBQUtkRDysd6B1FITKXpdJsrhU2_GeaTgNXGOsXA=="
    assert decrypt_secret(legacy, b"k" * 32) == "legacy-plugin-token"


def test_crypto_rejects_tampered_aes_gcm_payload():
    import base64
    import pytest
    from app.plugins.crypto import decrypt_secret, encrypt_secret

    token = encrypt_secret("plugin-secret", b"k" * 32)
    blob = bytearray(base64.urlsafe_b64decode(token.encode("ascii")))
    blob[-1] ^= 1
    tampered = base64.urlsafe_b64encode(blob).decode("ascii")
    with pytest.raises(ValueError, match="authentication failed"):
        decrypt_secret(tampered, b"k" * 32)

def test_corrupt_plugin_store_fails_closed(tmp_path: Path):
    from app.plugins.store import PluginStore

    store_path = tmp_path / "plugin_store.json"
    store_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Cannot load NEXA plugin store"):
        PluginStore(store_path)


def test_truncated_plugin_master_key_is_not_replaced(tmp_path: Path):
    from app.plugins.crypto import load_or_create_master_key

    key_path = tmp_path / "plugin.key"
    key_path.write_bytes(b"short")
    with pytest.raises(RuntimeError, match="corrupt or truncated"):
        load_or_create_master_key(str(key_path))
    assert key_path.read_bytes() == b"short"

