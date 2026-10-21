"""Shared auth dependencies for API lockdown (Part 15)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_auth_service, get_settings
from app.api.routes.auth import _extract_token
from app.auth.errors import UnauthorizedError
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import Settings

_bearer = HTTPBearer(auto_error=False)


def require_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRecord:
    """Always require a valid session (used for Plugin Hub and similar)."""
    token = _extract_token(request, credentials)
    if not token:
        raise UnauthorizedError()
    return auth.get_user_for_token(token)


def require_user_when_enforced(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRecord | None:
    """Require auth when TOKENS_ENFORCE is on (desktop/production default)."""
    token = _extract_token(request, credentials)
    if not token:
        if settings.tokens_enforce:
            raise UnauthorizedError()
        return None
    try:
        return auth.get_user_for_token(token)
    except UnauthorizedError:
        if settings.tokens_enforce:
            raise
        return None
