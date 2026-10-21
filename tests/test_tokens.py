"""Internal AI token / credits system tests."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from app.core.nexa_core import NexaCore
from app.main import app
from app.models.errors import ModelError
from app.providers.mock import MockProvider
from app.tokens.errors import (
    DailyTokenLimitError,
    InsufficientTokensError,
    MonthlyTokenLimitError,
    NegativeBalanceError,
    TokenAdminRequiredError,
)
from app.tokens.service import TokenService
from app.tokens.store import TokenStore


class _CapturingEmail(EmailService):
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        self.messages.append((to, subject, text_body))

    def last_code(self) -> str:
        body = self.messages[-1][2]
        match = re.search(r"\b(\d{6})\b", body)
        assert match, f"no code in email body: {body}"
        return match.group(1)


@pytest.fixture()
def token_service(tmp_path: Path) -> TokenService:
    store = TokenStore(tmp_path / "tokens.json")
    return TokenService(
        store,
        default_balance=50,
        default_daily_limit=100,
        default_monthly_limit=200,
        cost_chat=1,
        cost_agent=5,
        cost_image=10,
    )


def test_insufficient_tokens(token_service: TokenService):
    token_service.get_or_create_account("u1")
    token_service.admin_debit("u1", 50, actor_id="admin", reason="drain")
    assert token_service.get_balance("u1").balance == 0
    with pytest.raises(InsufficientTokensError):
        token_service.charge("u1", 1, request_id="r1", reason="chat")


def test_daily_and_monthly_limits(token_service: TokenService, tmp_path: Path):
    svc = TokenService(
        TokenStore(tmp_path / "lim.json"),
        default_balance=1000,
        default_daily_limit=5,
        default_monthly_limit=8,
    )
    for i in range(5):
        svc.charge("u1", 1, request_id=f"d-{i}", reason="chat")
    with pytest.raises(DailyTokenLimitError):
        svc.charge("u1", 1, request_id="d-overflow", reason="chat")

    svc2 = TokenService(
        TokenStore(tmp_path / "lim2.json"),
        default_balance=1000,
        default_daily_limit=100,
        default_monthly_limit=3,
    )
    for i in range(3):
        svc2.charge("u1", 1, request_id=f"m-{i}", reason="chat")
    with pytest.raises(MonthlyTokenLimitError):
        svc2.charge("u1", 1, request_id="m-overflow", reason="chat")


def test_duplicate_request_id_does_not_double_charge(token_service: TokenService):
    a1 = token_service.charge("u1", 10, request_id="same", reason="chat")
    a2 = token_service.charge("u1", 10, request_id="same", reason="chat")
    assert a1.balance == a2.balance == 40
    history = token_service.get_history("u1", limit=50)
    debits = [e for e in history if e.kind == "debit" and e.request_id == "same"]
    assert len(debits) == 1


def test_cost_schedule_and_usage_by_reason(token_service: TokenService):
    schedule = token_service.cost_schedule()
    assert schedule == {"chat": 1, "agent": 5, "image": 10, "default": 1}
    token_service.charge("u1", 1, request_id="c1", reason="chat")
    token_service.charge("u1", 1, request_id="c2", reason="chat")
    token_service.charge("u1", 5, request_id="a1", reason="agent")
    rows = token_service.usage_by_reason("u1")
    by_reason = {r["reason"]: r for r in rows}
    assert by_reason["chat"]["spent"] == 2
    assert by_reason["chat"]["count"] == 2
    assert by_reason["agent"]["spent"] == 5
    assert by_reason["agent"]["count"] == 1
    assert rows[0]["spent"] >= rows[-1]["spent"]


def test_parallel_charges_never_go_negative(tmp_path: Path):
    store = TokenStore(tmp_path / "race.json")
    svc = TokenService(
        store,
        default_balance=20,
        default_daily_limit=10_000,
        default_monthly_limit=10_000,
    )
    svc.get_or_create_account("u-race")

    def attempt(i: int) -> str:
        try:
            svc.charge("u-race", 1, request_id=f"p-{i}", reason="chat")
            return "ok"
        except InsufficientTokensError:
            return "reject"

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = [f.result() for f in as_completed([pool.submit(attempt, i) for i in range(40)])]

    assert results.count("ok") == 20
    assert results.count("reject") == 20
    assert svc.get_balance("u-race").balance == 0


def test_refund_after_ai_error(token_service: TokenService):
    before = token_service.get_balance("u1").balance
    with pytest.raises(ModelError):
        with token_service.charge_for_ai(
            "u1", 7, request_id="fail-1", reason="chat"
        ):
            raise ModelError("provider failed")
    after = token_service.get_balance("u1").balance
    assert after == before
    # second refund is no-op
    token_service.refund("fail-1")
    assert token_service.get_balance("u1").balance == before


def test_negative_balance_rejected(tmp_path: Path):
    store = TokenStore(tmp_path / "neg.json")
    svc = TokenService(store, default_balance=5)
    acc = svc.get_or_create_account("u1")
    with pytest.raises(NegativeBalanceError):

        def _bad(s: TokenStore):
            a = s.account_get("u1")
            assert a is not None
            s.apply_delta(
                user_id="u1",
                delta=-100,
                kind="debit",
                reason="force",
                request_id="x",
                actor_id=None,
                account=a,
            )

        store.run_atomic(_bad)
    assert svc.get_balance("u1").balance == acc.balance


def test_admin_credit_debit_and_limits(token_service: TokenService):
    token_service.get_or_create_account("u2")  # 50
    token_service.admin_credit("u2", 25, actor_id="admin", reason="promo")
    assert token_service.get_balance("u2").balance == 75
    token_service.admin_debit("u2", 10, actor_id="admin", reason="adjust")
    assert token_service.get_balance("u2").balance == 65
    lim = token_service.admin_set_limits(
        "u2", daily_limit=3, monthly_limit=9, actor_id="admin"
    )
    assert lim.daily_limit == 3
    assert lim.monthly_limit == 9


@pytest.fixture()
def auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("AUTH_STORE_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("TOKEN_STORE_PATH", str(tmp_path / "tokens.json"))
    monkeypatch.setenv("AUTH_SINGLE_USER", "false")
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("AUTH_BOOTSTRAP_FIRST_OWNER", "true")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_token_store.cache_clear()
    get_token_service.cache_clear()
    get_nexa_core.cache_clear()

    store = AuthStore(tmp_path / "auth.json")
    email = _CapturingEmail()
    auth = AuthService(
        store,
        email,
        code_ttl_seconds=900,
        resend_cooldown_seconds=0,
        max_verify_attempts=5,
        session_ttl_seconds=3600,
        app_name="NEXA",
        owner_emails=set(),
        bootstrap_first_owner=True,
        single_user=False,
        skip_email_verification=True,
    )
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=MockProvider(), settings=get_settings()
    )
    client = TestClient(app)
    yield client, auth, email
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_token_store.cache_clear()
    get_token_service.cache_clear()
    get_nexa_core.cache_clear()


def _register_and_login(
    client: TestClient, mail: _CapturingEmail, email: str, username: str
) -> None:
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
    assert r.status_code in {200, 201}, r.text
    # When AUTH_SKIP_EMAIL_VERIFICATION is on, no code email is sent.
    if mail.messages:
        code = mail.last_code()
        verified = client.post(
            "/api/v1/auth/verify-email",
            json={"email": email, "code": code},
        )
        assert verified.status_code == 200, verified.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secret123"},
    )
    assert login.status_code == 200, login.text


def test_admin_rights_http(auth_client):
    client, _auth, mail = auth_client
    _register_and_login(client, mail, "owner@nexa.test", "owner1")
    # first user is owner
    bal = client.get("/api/v1/tokens/balance")
    assert bal.status_code == 200
    assert bal.json()["balance"] >= 0

    # second user is not owner
    client.post("/api/v1/auth/logout")
    _register_and_login(client, mail, "user2@nexa.test", "user2")
    forbidden = client.post(
        "/api/v1/tokens/admin/credit",
        json={"user_id": "x", "amount": 10, "reason": "nope"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"] == "TokenAdminRequired"

    # user cannot mutate own balance via admin endpoint
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    uid = me.json()["user"]["id"]
    assert (
        client.post(
            "/api/v1/tokens/admin/debit",
            json={"user_id": uid, "amount": 1, "reason": "self"},
        ).status_code
        == 403
    )


def test_chat_charges_and_refunds_on_error(auth_client, monkeypatch):
    client, _auth, mail = auth_client
    _register_and_login(client, mail, "chat@nexa.test", "chatuser")
    before = client.get("/api/v1/tokens/balance").json()["balance"]

    ok = client.post(
        "/api/v1/chat",
        json={"message": "hi", "request_id": "chat-ok-1"},
    )
    assert ok.status_code == 200, ok.text
    mid = client.get("/api/v1/tokens/balance").json()["balance"]
    assert mid == before - 1

    class _Broken(MockProvider):
        async def generate(self, messages):
            raise RuntimeError("boom")

    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=_Broken(), settings=get_settings()
    )
    get_nexa_core.cache_clear()
    bad = client.post(
        "/api/v1/chat",
        json={"message": "fail please", "request_id": "chat-fail-1"},
    )
    assert bad.status_code == 502
    after = client.get("/api/v1/tokens/balance").json()["balance"]
    assert after == mid  # refunded
