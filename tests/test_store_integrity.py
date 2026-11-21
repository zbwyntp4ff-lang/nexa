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
