"""Persistent JSON stores must fail closed rather than silently reset state."""
from __future__ import annotations

import pytest

from app.billing.store import BillingStore
from app.profile.store import ProfileStore
from app.tokens.store import TokenStore


@pytest.mark.parametrize(
    ("store_type", "filename", "error_fragment"),
    [
        (TokenStore, "tokens.json", "token store"),
        (BillingStore, "billing.json", "billing store"),
        (ProfileStore, "profiles.json", "profile store"),
    ],
)
def test_corrupt_store_fails_closed_and_preserves_original_file(
    tmp_path, store_type, filename, error_fragment
):
    path = tmp_path / filename
    corrupt = b'{"truncated": '
    path.write_bytes(corrupt)

    with pytest.raises(RuntimeError, match=error_fragment):
        store_type(path)

    assert path.read_bytes() == corrupt


def test_token_store_does_not_mutate_when_file_lock_fails(tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    store = TokenStore(path)

    def fail_lock(_lock_file):
        raise OSError("simulated lock failure")

    monkeypatch.setattr(TokenStore, "_acquire_file_lock", staticmethod(fail_lock))
    with pytest.raises(RuntimeError, match="Cannot acquire NEXA token-store lock"):
        store.run_atomic(lambda current: current.account_set(
            __import__("app.tokens.models", fromlist=["TokenAccount"]).TokenAccount(
                user_id="u1", balance=100
            )
        ))
    assert not path.exists()
