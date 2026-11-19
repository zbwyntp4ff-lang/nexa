"""OAuth providers (Google / GitHub / Apple) — env-gated, real HTTP only."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx

from app.auth.credentials import load_google_oauth
from app.auth.errors import AuthError, ValidationAuthError

ProviderId = Literal["google", "github", "apple"]


class OAuthNotConfiguredError(AuthError):
    default_message = "This sign-in provider is not configured."
    code = "OAuthNotConfigured"


class OAuthExchangeError(AuthError):
    default_message = "Could not complete OAuth sign-in."
    code = "OAuthExchangeError"


@dataclass(frozen=True)
class OAuthProfile:
    provider: ProviderId
    subject: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str
    username_hint: str


@dataclass(frozen=True)
class ProviderConfig:
    id: ProviderId
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: str
    extra_auth_params: dict[str, str]


def _configured(client_id: str | None, client_secret: str | None) -> bool:
    return bool((client_id or "").strip() and (client_secret or "").strip())


def _as_bool(value: Any, *, default: bool = False) -> bool:
    """Parse provider booleans without treating the string "false" as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def provider_configs(settings: Any) -> dict[ProviderId, ProviderConfig]:
    out: dict[ProviderId, ProviderConfig] = {}
    google = load_google_oauth(settings)
    if google:
        google_id, google_secret = google
        out["google"] = ProviderConfig(
            id="google",
            client_id=google_id,
            client_secret=google_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes="openid email profile",
            extra_auth_params={"access_type": "online", "prompt": "select_account"},
        )
    if _configured(settings.oauth_github_client_id, settings.oauth_github_client_secret):
        out["github"] = ProviderConfig(
            id="github",
            client_id=settings.oauth_github_client_id.strip(),
            client_secret=settings.oauth_github_client_secret.strip(),
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scopes="read:user user:email",
            extra_auth_params={},
        )
    if _configured(settings.oauth_apple_client_id, settings.oauth_apple_client_secret):
        out["apple"] = ProviderConfig(
            id="apple",
            client_id=settings.oauth_apple_client_id.strip(),
            client_secret=settings.oauth_apple_client_secret.strip(),
            authorize_url="https://appleid.apple.com/auth/authorize",
            token_url="https://appleid.apple.com/auth/token",
            scopes="name email",
            extra_auth_params={"response_mode": "form_post"},
        )
    return out


def list_provider_status(settings: Any) -> list[dict[str, Any]]:
    cfg = provider_configs(settings)
    labels = {
        "google": "Google",
        "github": "GitHub",
        "apple": "Apple",
    }
    return [
        {
            "id": pid,
            "label": labels[pid],
            "enabled": pid in cfg,
            "kind": "oauth",
        }
        for pid in ("google", "github", "apple")
    ]


def build_authorize_url(
    settings: Any,
    provider: ProviderId,
    *,
    state: str,
    redirect_uri: str,
) -> str:
    cfg = provider_configs(settings).get(provider)
    if not cfg:
        raise OAuthNotConfiguredError(f"{provider} sign-in is not configured on this server.")
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg.scopes,
        "state": state,
        **cfg.extra_auth_params,
    }
    return f"{cfg.authorize_url}?{urlencode(params)}"


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


async def exchange_code(
    settings: Any,
    provider: ProviderId,
    *,
    code: str,
    redirect_uri: str,
    apple_user: dict[str, Any] | None = None,
) -> OAuthProfile:
    cfg = provider_configs(settings).get(provider)
    if not cfg:
        raise OAuthNotConfiguredError(f"{provider} sign-in is not configured on this server.")
    if not code.strip():
        raise ValidationAuthError("Missing OAuth authorization code.")

    async with httpx.AsyncClient(timeout=20.0) as client:
        if provider == "google":
            return await _google_profile(client, cfg, code=code, redirect_uri=redirect_uri)
        if provider == "github":
            return await _github_profile(client, cfg, code=code, redirect_uri=redirect_uri)
        if provider == "apple":
            return await _apple_profile(client, cfg, code=code, redirect_uri=redirect_uri, apple_user=apple_user)
    raise ValidationAuthError("Unknown OAuth provider.")


async def _token_post(
    client: httpx.AsyncClient,
    cfg: ProviderConfig,
    *,
    code: str,
    redirect_uri: str,
    accept_json: bool = True,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"} if accept_json else {}
    response = await client.post(
        cfg.token_url,
        data={
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers=headers,
    )
    if response.status_code >= 400:
        raise OAuthExchangeError("OAuth token exchange failed.")
    data = response.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        # Apple may return id_token without access_token in some setups
        if isinstance(data, dict) and data.get("id_token"):
            return data
        raise OAuthExchangeError("OAuth provider did not return an access token.")
    return data


async def _google_profile(
    client: httpx.AsyncClient,
    cfg: ProviderConfig,
    *,
    code: str,
    redirect_uri: str,
) -> OAuthProfile:
    token = await _token_post(client, cfg, code=code, redirect_uri=redirect_uri)
    userinfo = await client.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    if userinfo.status_code >= 400:
        raise OAuthExchangeError("Could not load Google profile.")
    data = userinfo.json()
    email = str(data.get("email") or "").strip().lower()
    if not email:
        raise OAuthExchangeError("Google account has no email.")
    given = str(data.get("given_name") or data.get("name") or "User").strip() or "User"
    family = str(data.get("family_name") or "").strip() or "Google"
    sub = str(data.get("sub") or "").strip()
    if not sub:
        raise OAuthExchangeError("Google account missing subject.")
    local = email.split("@", 1)[0]
    return OAuthProfile(
        provider="google",
        subject=sub,
        email=email,
        email_verified=_as_bool(data.get("email_verified"), default=False),
        first_name=given[:64],
        last_name=family[:64],
        username_hint=_slug(local),
    )


async def _github_profile(
    client: httpx.AsyncClient,
    cfg: ProviderConfig,
    *,
    code: str,
    redirect_uri: str,
) -> OAuthProfile:
    token = await _token_post(client, cfg, code=code, redirect_uri=redirect_uri)
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    user_resp = await client.get("https://api.github.com/user", headers=headers)
    if user_resp.status_code >= 400:
        raise OAuthExchangeError("Could not load GitHub profile.")
    data = user_resp.json()
    sub = str(data.get("id") or "").strip()
    if not sub:
        raise OAuthExchangeError("GitHub account missing id.")
    email = ""
    email_verified = False
    public_email = str(data.get("email") or "").strip().lower()
    emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
    if emails_resp.status_code < 400:
        rows = emails_resp.json() if isinstance(emails_resp.json(), list) else []
        for row in rows:
            if isinstance(row, dict) and row.get("primary") and row.get("verified") and row.get("email"):
                email = str(row["email"]).strip().lower()
                email_verified = True
                break
        if not email:
            for row in rows:
                if isinstance(row, dict) and row.get("verified") and row.get("email"):
                    email = str(row["email"]).strip().lower()
                    email_verified = True
                    break
    if not email and public_email:
        # Profile email without /user/emails verified flag — do not trust as verified.
        email = public_email
        email_verified = False
    if not email:
        raise OAuthExchangeError("GitHub account has no email. Make email public or grant user:email.")
    name = str(data.get("name") or data.get("login") or "User").strip()
    parts = name.split(None, 1)
    first = parts[0][:64] if parts else "User"
    last = (parts[1] if len(parts) > 1 else "GitHub")[:64]
    login = str(data.get("login") or email.split("@", 1)[0])
    return OAuthProfile(
        provider="github",
        subject=sub,
        email=email,
        email_verified=email_verified,
        first_name=first,
        last_name=last,
        username_hint=_slug(login),
    )


async def _apple_profile(
    client: httpx.AsyncClient,
    cfg: ProviderConfig,
    *,
    code: str,
    redirect_uri: str,
    apple_user: dict[str, Any] | None = None,
) -> OAuthProfile:
    token = await _token_post(client, cfg, code=code, redirect_uri=redirect_uri)
    id_token = str(token.get("id_token") or "")
    if not id_token:
        raise OAuthExchangeError("Apple did not return an id_token.")
    # Verify Apple's signature and standard claims before trusting the identity.
    try:
        import jwt
        from jwt.algorithms import RSAAlgorithm

        keys_response = await client.get("https://appleid.apple.com/auth/keys")
        keys_response.raise_for_status()
        jwks = keys_response.json()
        header = jwt.get_unverified_header(id_token)
        key_data = next(
            key for key in jwks.get("keys", [])
            if key.get("kid") == header.get("kid") and key.get("kty") == "RSA"
        )
        signing_key = RSAAlgorithm.from_jwk(key_data)
        payload = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=cfg.client_id,
            issuer="https://appleid.apple.com",
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except Exception as exc:
        raise OAuthExchangeError("Apple identity token verification failed.") from exc
    sub = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    if not sub:
        raise OAuthExchangeError("Apple account missing subject.")
    if not email:
        email = f"{sub[:16]}@privaterelay.appleid.com"
    local = email.split("@", 1)[0]
    name_data = apple_user.get("name", {}) if isinstance(apple_user, dict) else {}
    first_name = str(name_data.get("firstName") or "Apple").strip()[:64] or "Apple"
    last_name = str(name_data.get("lastName") or "User").strip()[:64] or "User"
    return OAuthProfile(
        provider="apple",
        subject=sub,
        email=email,
        email_verified=_as_bool(payload.get("email_verified"), default=False),
        first_name=first_name,
        last_name=last_name,
        username_hint=_slug(local),
    )


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value.strip())
    cleaned = cleaned.strip("_")[:24] or "user"
    if cleaned[0].isdigit():
        cleaned = f"u_{cleaned}"
    return cleaned.lower()
