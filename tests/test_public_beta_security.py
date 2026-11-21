from __future__ import annotations

import pytest
from starlette.requests import Request

from app.api.security_deps import require_user_when_enforced
from app.auth.errors import UnauthorizedError
from app.config.settings import Settings


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/voice/synthesize",
            "raw_path": b"/api/v1/voice/synthesize",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8420),
        }
    )


def test_anonymous_mutating_endpoint_requires_session_when_enforced() -> None:
    settings = Settings(_env_file=None, TOKENS_ENFORCE=True)
    with pytest.raises(UnauthorizedError):
        require_user_when_enforced(_request(), None, None, settings)


def test_local_desktop_mode_can_still_run_without_session() -> None:
    settings = Settings(_env_file=None, TOKENS_ENFORCE=False)
    assert require_user_when_enforced(_request(), None, None, settings) is None
