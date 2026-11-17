"""Cross-user isolation tests for public multi-user cloud readiness.

Attempts by user B to read/modify user A's memory, knowledge, conversations,
and feedback must fail (404/empty/403) — never leak data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_auth_service,
    get_auth_store,
    get_nexa_core,
    get_token_service,
    get_token_store,
)
from app.auth.email import EmailService
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.config.settings import get_settings
from app.conversations.store import get_conversation_store
from app.knowledge.knowledge_base import get_knowledge_base
from app.main import app
from app.memory.manager import get_memory_manager as _gmm


class CapturingEmail(EmailService):
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        self.messages.append((to, subject, text_body))

    def last_code(self) -> str:
        body = self.messages[-1][2]
        match = re.search(r"\b(\d{6})\b", body)
        assert match
        return match.group(1)


@pytest.fixture()
def multi_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.api.deps import get_workflow_engine
    from app.attachments.manager import get_attachment_manager
    from app.db.engine import get_database
    from app.plugins.manager import get_plugin_manager

    monkeypatch.setenv("AUTH_STORE_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("AUTH_LEGAL_DIR", str(tmp_path / "legal"))
    monkeypatch.setenv("MEMORY_STORE_PATH", str(tmp_path / "memory.json"))
    monkeypatch.setenv("MEMORY_BACKEND", "sql")
    monkeypatch.setenv("TOKEN_STORE_PATH", str(tmp_path / "tokens.json"))
    monkeypatch.setenv("PROFILE_STORE_PATH", str(tmp_path / "profiles.json"))
    monkeypatch.setenv("KNOWLEDGE_STORE_PATH", str(tmp_path / "kv.json"))
    monkeypatch.setenv("KNOWLEDGE_DOCUMENTS_PATH", str(tmp_path / "kd.json"))
    monkeypatch.setenv("PLUGIN_STORE_PATH", str(tmp_path / "plugins.json"))
    monkeypatch.setenv("PLUGIN_KEY_PATH", str(tmp_path / "plugin.key"))
    monkeypatch.setenv("PLUGIN_WORKSPACE_DIR", str(tmp_path / "plugin_ws"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'nexa.db'}")
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("AUTH_BOOTSTRAP_FIRST_OWNER", "true")
    monkeypatch.setenv("AUTH_SINGLE_USER", "false")
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "0")
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_token_store.cache_clear()
    get_token_service.cache_clear()
    get_nexa_core.cache_clear()
    get_knowledge_base.cache_clear()
    _gmm.cache_clear()
    get_conversation_store.cache_clear()
    get_database.cache_clear()
    get_plugin_manager.cache_clear()
    get_workflow_engine.cache_clear()
    get_attachment_manager.cache_clear()

    mail = CapturingEmail()
    store = AuthStore(tmp_path / "auth.json")
    service = AuthService(
        store,
        mail,
        code_ttl_seconds=900,
        resend_cooldown_seconds=1,
        max_verify_attempts=5,
        session_ttl_seconds=3600,
        app_name="NEXA Test",
        bootstrap_first_owner=True,
        single_user=False,
        skip_email_verification=True,
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_auth_store] = lambda: store
    client = TestClient(app)

    def register(email: str, username: str) -> str:
        r = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "T",
                "last_name": "U",
                "username": username,
                "email": email,
                "password": "Secret123",
                "confirm_password": "Secret123",
                "accept_terms": True,
                "accept_privacy": True,
                "accept_license": True,
            },
        )
        assert r.status_code in (200, 201), r.text
        token = r.cookies.get("nexa_session")
        if not token:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "Secret123"},
            )
            assert login.status_code == 200, login.text
            token = login.cookies.get("nexa_session")
        assert token
        return token

    token_a = register("alice@nexa.test", "alice_iso")
    token_b = register("bob@nexa.test", "bob_iso")
    yield client, token_a, token_b

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_token_store.cache_clear()
    get_token_service.cache_clear()
    get_nexa_core.cache_clear()
    get_knowledge_base.cache_clear()
    _gmm.cache_clear()
    get_conversation_store.cache_clear()
    get_database.cache_clear()
    get_plugin_manager.cache_clear()
    get_workflow_engine.cache_clear()
    get_attachment_manager.cache_clear()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_memory_isolation(multi_user):
    client, token_a, token_b = multi_user
    created = client.post(
        "/api/v1/memory",
        headers=_h(token_a),
        json={"content": "Alice private fact about Orion", "type": "long_term", "force": True},
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["item"]["id"]

    listed_b = client.get("/api/v1/memory?query=Orion&limit=20", headers=_h(token_b))
    assert listed_b.status_code == 200
    assert listed_b.json()["count"] == 0

    deleted = client.delete(f"/api/v1/memory/{item_id}", headers=_h(token_b))
    assert deleted.status_code in (404, 403, 400)

    still = client.get("/api/v1/memory?query=Orion&limit=20", headers=_h(token_a))
    assert still.json()["count"] >= 1


@pytest.mark.asyncio
async def test_knowledge_isolation(multi_user):
    client, token_a, token_b = multi_user
    note = client.post(
        "/api/v1/knowledge/notes",
        headers=_h(token_a),
        json={"title": "alice-doc", "text": "Unique zebra pineapple belongs to Alice only."},
    )
    assert note.status_code == 200, note.text
    doc_id = note.json()["id"]

    list_b = client.get("/api/v1/knowledge/documents", headers=_h(token_b))
    assert list_b.status_code == 200
    assert all(d["id"] != doc_id for d in list_b.json())

    get_b = client.get(f"/api/v1/knowledge/sources/{doc_id}", headers=_h(token_b))
    assert get_b.status_code == 404

    search_b = client.post(
        "/api/v1/knowledge/search",
        headers=_h(token_b),
        json={"query": "zebra pineapple"},
    )
    assert search_b.status_code == 200
    assert search_b.json()["insufficient"] or not search_b.json()["citations"]

    del_b = client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=_h(token_b))
    assert del_b.status_code == 404

    get_a = client.get(f"/api/v1/knowledge/sources/{doc_id}", headers=_h(token_a))
    assert get_a.status_code == 200


def test_conversation_isolation(multi_user):
    client, token_a, token_b = multi_user
    created = client.put(
        "/api/v1/conversations",
        headers=_h(token_a),
        json={"title": "Alice chat", "mode": "chat", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    get_b = client.get(f"/api/v1/conversations/{cid}", headers=_h(token_b))
    assert get_b.status_code == 404

    upd_b = client.put(
        "/api/v1/conversations",
        headers=_h(token_b),
        json={"id": cid, "title": "hacked", "messages": []},
    )
    assert upd_b.status_code == 404

    del_b = client.delete(f"/api/v1/conversations/{cid}", headers=_h(token_b))
    assert del_b.status_code == 404

    get_a = client.get(f"/api/v1/conversations/{cid}", headers=_h(token_a))
    assert get_a.status_code == 200
    assert get_a.json()["title"] == "Alice chat"


def test_feedback_isolation(multi_user):
    client, token_a, token_b = multi_user
    fb = client.post(
        "/api/v1/knowledge-core/feedback",
        headers=_h(token_a),
        json={
            "rating": "useful",
            "user_request": "q",
            "nexa_response": "a secret alice note",
            "user_id": "should-be-ignored",
        },
    )
    assert fb.status_code == 200, fb.text
    assert fb.json()["user_id"] != "should-be-ignored"

    list_b = client.get("/api/v1/knowledge-core/feedback?limit=50", headers=_h(token_b))
    assert list_b.status_code == 200
    assert all("secret alice" not in e.get("nexa_response", "") for e in list_b.json())


def test_account_delete_requires_confirm(multi_user):
    client, token_a, _token_b = multi_user
    denied = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_h(token_a),
        json={"confirm": "nope"},
    )
    assert denied.status_code == 400
    me = client.get("/api/v1/auth/me", headers=_h(token_a))
    assert me.status_code == 200


def test_account_delete_wipes_owned_data(multi_user):
    client, token_a, token_b = multi_user
    client.post(
        "/api/v1/memory",
        headers=_h(token_a),
        json={"content": "wipe me soon", "type": "long_term", "force": True},
    )
    client.put(
        "/api/v1/conversations",
        headers=_h(token_a),
        json={"title": "gone", "mode": "chat", "messages": [{"role": "user", "content": "x"}]},
    )
    deleted = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_h(token_a),
        json={"confirm": "DELETE"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    report = deleted.json().get("report") or {}
    assert "limitations" in report

    me = client.get("/api/v1/auth/me", headers=_h(token_a))
    assert me.status_code in (401, 403)

    # Bob still works and still has no Alice data
    me_b = client.get("/api/v1/auth/me", headers=_h(token_b))
    assert me_b.status_code == 200
    mem_b = client.get("/api/v1/memory?query=wipe&limit=20", headers=_h(token_b))
    assert mem_b.json()["count"] == 0


def test_unauthenticated_denied_when_enforced(multi_user):
    # Fresh client — no session cookies from registration.
    bare = TestClient(app)
    assert bare.get("/api/v1/memory").status_code in (401, 403)
    assert bare.get("/api/v1/conversations").status_code in (401, 403)
    assert bare.get("/api/v1/plugins").status_code in (401, 403)
    assert bare.get("/api/v1/auth/me").status_code in (401, 403)


def test_plugin_connection_isolation(multi_user):
    client, token_a, token_b = multi_user
    conn = client.post(
        "/api/v1/plugins/vscode/connect",
        headers=_h(token_a),
        json={"permissions": ["files.read"]},
    )
    assert conn.status_code == 200, conn.text
    alice_card = conn.json()
    assert alice_card.get("enabled") is True or alice_card.get("status") in (
        "connected",
        "connected_limited",
        "ready",
        "ok",
    )

    card_b = client.get("/api/v1/plugins/vscode", headers=_h(token_b))
    assert card_b.status_code == 200
    body_b = card_b.json()
    # Bob must not inherit Alice's connection.
    assert body_b.get("enabled") in (False, None)
    assert body_b.get("status") not in ("connected", "connected_limited")

    disc_b = client.post("/api/v1/plugins/vscode/disconnect", headers=_h(token_b))
    assert disc_b.status_code == 200
    still_a = client.get("/api/v1/plugins/vscode", headers=_h(token_a))
    assert still_a.status_code == 200
    assert still_a.json().get("enabled") is True or still_a.json().get("status") in (
        "connected",
        "connected_limited",
        "ready",
        "ok",
    )


def test_workflow_isolation(multi_user):
    client, token_a, token_b = multi_user
    created = client.post(
        "/api/v1/workflows",
        headers=_h(token_a),
        json={"goal": "Alice private workflow goal", "name": "alice-wf"},
    )
    assert created.status_code == 200, created.text
    wid = created.json()["id"]

    list_b = client.get("/api/v1/workflows", headers=_h(token_b))
    assert list_b.status_code == 200
    assert all(w["id"] != wid for w in list_b.json())

    get_b = client.get(f"/api/v1/workflows/{wid}", headers=_h(token_b))
    assert get_b.status_code == 404

    start_b = client.post(f"/api/v1/workflows/{wid}/start", headers=_h(token_b))
    assert start_b.status_code == 404

    get_a = client.get(f"/api/v1/workflows/{wid}", headers=_h(token_a))
    assert get_a.status_code == 200
    assert get_a.json()["name"] == "alice-wf"


def test_profile_isolation(multi_user):
    client, token_a, token_b = multi_user
    put_a = client.patch(
        "/api/v1/profile",
        headers=_h(token_a),
        json={
            "display_name": "Alice Only",
            "ai": {"preferred_name": "AliciaSecret", "personalization_enabled": True},
        },
    )
    assert put_a.status_code == 200, put_a.text

    get_b = client.get("/api/v1/profile", headers=_h(token_b))
    assert get_b.status_code == 200
    blob = json.dumps(get_b.json())
    assert "Alice Only" not in blob
    assert "AliciaSecret" not in blob


def test_conversation_list_scoped(multi_user):
    client, token_a, token_b = multi_user
    client.put(
        "/api/v1/conversations",
        headers=_h(token_a),
        json={
            "title": "Alice list chat",
            "mode": "chat",
            "messages": [{"role": "user", "content": "secret-list-marker"}],
        },
    )
    list_b = client.get("/api/v1/conversations", headers=_h(token_b))
    assert list_b.status_code == 200
    assert all(c.get("title") != "Alice list chat" for c in list_b.json())
    list_a = client.get("/api/v1/conversations", headers=_h(token_a))
    assert any(c.get("title") == "Alice list chat" for c in list_a.json())


def test_logout_invalidates_session(multi_user):
    client, token_a, _token_b = multi_user
    out = client.post("/api/v1/auth/logout", headers=_h(token_a))
    assert out.status_code == 200
    me = client.get("/api/v1/auth/me", headers=_h(token_a))
    assert me.status_code in (401, 403)


def test_health_without_ollama():
    """Cloud health must not require Ollama."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body.get("ollama_required") is False or body.get("ai_provider") not in (
        None,
    )
