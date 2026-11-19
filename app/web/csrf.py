"""Origin validation for cookie-authenticated state-changing requests.

SameSite cookies are defense in depth, not a complete CSRF boundary: sibling
subdomains are same-site, and deployments may explicitly use SameSite=None.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_APPLE_FORM_POST_CALLBACK = "/api/v1/auth/oauth/apple/callback"


class CookieCSRFMiddleware(BaseHTTPMiddleware):
    """Require a configured frontend Origin for cookie-authenticated writes.

    Bearer-token clients are not exposed to ambient-cookie CSRF. Apple's
    cross-site form_post callback is exempt because its one-time OAuth state
    is the CSRF defense for that protocol endpoint.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method.upper() not in _UNSAFE_METHODS:
            return await call_next(request)
        if request.url.path == _APPLE_FORM_POST_CALLBACK:
            return await call_next(request)

        from app.config.settings import get_settings

        settings = get_settings()
        if not request.cookies.get(settings.auth_session_cookie_name):
            return await call_next(request)

        origin = (request.headers.get("origin") or "").strip()
        if not origin:
            referer = (request.headers.get("referer") or "").strip()
            if referer:
                parsed = urlsplit(referer)
                if parsed.scheme and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"
            else:
                # Modern browsers send Origin on unsafe requests. For older
                # clients without Origin/Referer, honor Fetch Metadata when
                # available and reject cross-site/same-site ambiguous writes;
                # non-browser API clients without Fetch Metadata remain usable.
                fetch_site = (request.headers.get("sec-fetch-site") or "").lower()
                if fetch_site in {"cross-site", "same-site"}:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "csrf_origin_rejected",
                            "message": "Cross-site cookie-authenticated actions are not allowed.",
                        },
                    )
                return await call_next(request)

        allowed = {
            value.strip().rstrip("/")
            for value in settings.cors_allowed_origins
            if value and value.strip()
        }
        if not origin or origin.rstrip("/") not in allowed:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_origin_rejected",
                    "message": "Request origin is not allowed for cookie-authenticated actions.",
                },
            )
        return await call_next(request)
