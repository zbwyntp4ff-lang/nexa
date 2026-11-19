"""Authentication HTTP API — register, verify, login, session."""
from __future__ import annotations

import json
from typing import Annotated, Literal
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service
from app.auth.credentials import save_google_oauth
from app.auth.errors import UnauthorizedError, ValidationAuthError
from app.auth.legal import get_document, list_documents, load_holder, save_holder
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.models.auth_api import (
    AuthStatusResponse,
    DeleteAccountRequest,
    DeviceApproveRequest,
    DeviceDenyRequest,
    DeviceStartResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    OAuthStartResponse,
    PasskeyVerifyRequest,
    ProviderInfo,
    ProvidersResponse,
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    ResendCodeResponse,
    ResetPasswordRequest,
    UserPublic,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _cookie_name() -> str:
    return get_settings().auth_session_cookie_name


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    same_site = settings.auth_cookie_samesite.lower()
    # Starlette expects literal casing for samesite
    samesite_literal = "lax" if same_site == "lax" else "strict" if same_site == "strict" else "none"
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure or samesite_literal == "none",
        samesite=samesite_literal,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=_cookie_name(), path="/")


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials
    return request.cookies.get(_cookie_name())


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRecord:
    token = _extract_token(request, credentials)
    return auth.get_user_for_token(token)


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthStatusResponse:
    return AuthStatusResponse(**auth.status())


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> RegisterResponse:
    from app.auth.rate_limit import register_ip_limiter

    ip = request.client.host if request.client else "unknown"
    register_ip_limiter.check(f"reg:{ip}")
    result = auth.register(
        first_name=body.first_name,
        last_name=body.last_name,
        username=body.username,
        email=body.email,
        password=body.password,
        confirm_password=body.confirm_password,
        accept_terms=body.accept_terms,
        accept_privacy=body.accept_privacy,
        accept_license=body.accept_license,
    )
    # Single-user owner setup: activate session immediately (no email code).
    if result.get("ready"):
        login = auth.login(
            email=body.email,
            password=body.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
        _set_session_cookie(response, login["session_token"])
        return RegisterResponse(
            user=UserPublic(**login["user"]),
            email=result["email"],
            verification_id="",
            code_expires_at=result["code_expires_at"],
            resend_available_at=result["resend_available_at"],
            ready=True,
            message="Owner account ready.",
        )
    return RegisterResponse(
        user=UserPublic(**result["user"]),
        email=result["email"],
        verification_id=result["verification_id"],
        code_expires_at=result["code_expires_at"],
        resend_available_at=result["resend_available_at"],
        ready=False,
    )


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    body: VerifyEmailRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> VerifyEmailResponse:
    result = auth.verify_email(email=body.email, code=body.code)
    return VerifyEmailResponse(user=UserPublic(**result["user"]))


@router.post("/resend-code", response_model=ResendCodeResponse)
async def resend_code(
    body: ResendCodeRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> ResendCodeResponse:
    result = auth.resend_verification(email=body.email)
    return ResendCodeResponse(
        email=body.email,
        sent=True,
        # Always false in the public response to avoid account enumeration.
        already_verified=False,
        code_expires_at=None,
        resend_available_at=result["resend_available_at"],
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    from app.auth.rate_limit import login_account_limiter, login_ip_limiter

    client_ip = request.client.host if request.client else "unknown"
    login_ip_limiter.check(f"login:ip:{client_ip}")
    login_account_limiter.check(f"login:account:{body.email.strip().lower()}")
    result = auth.login(
        email=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip,
    )
    _set_session_cookie(response, result["session_token"])
    return LoginResponse(
        user=UserPublic(**result["user"]),
        expires_at=result["expires_at"],
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    token = _extract_token(request, credentials)
    auth.logout(token)
    _clear_session_cookie(response)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MeResponse:
    # Refresh cookie max-age after sliding session touch so the browser keeps
    # the session until the user explicitly logs out.
    token = _extract_token(request, credentials)
    if token:
        _set_session_cookie(response, token)
    return MeResponse(user=UserPublic(**auth.public_user(user)))


@router.delete("/account")
async def delete_account(
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    body: DeleteAccountRequest,
) -> dict:
    """Permanently delete the signed-in account and related user-scoped data.

    Requires ``{"confirm":"DELETE"}`` in the JSON body (case-insensitive).
    Does not remove data from backups/replicas; see wipe report ``limitations``.
    """
    from app.api.deps import (
        get_auth_store,
        get_memory_manager_dep,
        get_profile_store,
        get_token_store,
    )
    from app.auth.errors import AccountDeleteConfirmError
    from app.knowledge.knowledge_base import get_knowledge_base
    from app.privacy.account_wipe import wipe_user_account

    if body.confirm.strip().upper() != "DELETE":
        raise AccountDeleteConfirmError()

    report = wipe_user_account(
        user_id=user.id,
        auth_store=get_auth_store(),
        memory=get_memory_manager_dep(),
        knowledge=get_knowledge_base(),
        tokens=get_token_store(),
        profiles=get_profile_store(),
    )
    token = _extract_token(request, credentials)
    if token:
        auth.logout(token)
    _clear_session_cookie(response)
    return {"deleted": True, "report": report.model_dump()}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    result = auth.request_password_reset(email=body.email)
    return MessageResponse(
        message="If an account exists for that email, a reset code has been sent.",
        email=body.email,
        # Never return code_expires_at here — it differed for known vs unknown emails.
        code_expires_at=None,
        resend_available_at=result.get("resend_available_at"),
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    auth.reset_password(
        email=body.email,
        code=body.code,
        password=body.password,
        confirm_password=body.confirm_password,
    )
    return MessageResponse(message="Password updated. You can sign in now.")


@router.get("/providers", response_model=ProvidersResponse)
async def providers(
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> ProvidersResponse:
    data = auth.list_login_providers()
    return ProvidersResponse(
        oauth=[ProviderInfo(**p) for p in data["oauth"]],
        device=ProviderInfo(**data["device"]),
        passkey=ProviderInfo(**data["passkey"]),
        password=ProviderInfo(**data["password"]),
    )


@router.get("/oauth/{provider}/start", response_model=OAuthStartResponse)
async def oauth_start(
    provider: Literal["google", "github", "apple"],
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> OAuthStartResponse:
    origin = (request.headers.get("origin") or "").strip()
    result = auth.start_oauth(provider, return_origin=origin)  # type: ignore[arg-type]
    return OAuthStartResponse(**result)


async def _complete_oauth_callback(
    provider: Literal["google", "github", "apple"],
    request: Request,
    auth: AuthService,
    *,
    code: str | None,
    state: str | None,
    error: str | None,
    apple_user: dict | None = None,
) -> RedirectResponse:
    settings = get_settings()
    public_base = (
        settings.auth_public_base_url or settings.billing_public_base_url or ""
    ).rstrip("/") or "http://localhost:4820"
    if error or not code or not state:
        msg = quote(error or "oauth_denied")
        return RedirectResponse(url=f"{public_base}/?auth_error={msg}", status_code=302)
    try:
        result = await auth.finish_oauth(
            provider,  # type: ignore[arg-type]
            code=code,
            state=state,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            apple_user=apple_user,
        )
    except Exception as exc:
        msg = quote(getattr(exc, "code", "oauth_failed"))
        return RedirectResponse(url=f"{public_base}/?auth_error={msg}", status_code=302)
    frontend = auth.oauth_return_url(str(result.get("return_origin") or ""), public_base)
    # Never put the live session token in the URL (history/Referer leak).
    redirect = RedirectResponse(url=f"{frontend}/?oauth=ok", status_code=302)
    _set_session_cookie(redirect, result["session_token"])
    return redirect


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: Literal["google", "github", "apple"],
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return await _complete_oauth_callback(
        provider, request, auth, code=code, state=state, error=error
    )


@router.post("/oauth/{provider}/callback")
async def oauth_callback_form_post(
    provider: Literal["google", "github", "apple"],
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> RedirectResponse:
    # Sign in with Apple posts authorization results as form-urlencoded data.
    apple_user = None
    try:
        form = await request.form()
        code = str(form.get("code") or "") or None
        state = str(form.get("state") or "") or None
        error = str(form.get("error") or "") or None
        raw_user = form.get("user")
        if provider == "apple" and raw_user:
            parsed_user = json.loads(str(raw_user))
            if isinstance(parsed_user, dict):
                apple_user = parsed_user
    except Exception:
        code = state = error = None
    return await _complete_oauth_callback(
        provider, request, auth, code=code, state=state, error=error,
        apple_user=apple_user,
    )


class _DeviceStartBody(BaseModel):
    origin: str | None = None


@router.post("/device/start", response_model=DeviceStartResponse)
async def device_start(
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    body: _DeviceStartBody | None = None,
) -> DeviceStartResponse:
    origin = (body.origin if body else None) or (request.headers.get("origin") or None)
    return DeviceStartResponse(**auth.start_device_login(ui_origin=origin))


class _DevicePollBody(BaseModel):
    device_code: str = Field(..., min_length=8, max_length=128)


@router.post("/device/poll", response_model=LoginResponse)
async def device_poll(
    body: _DevicePollBody,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    result = auth.poll_device_login(body.device_code)
    _set_session_cookie(response, result["session_token"])
    return LoginResponse(
        user=UserPublic(**result["user"]),
        expires_at=result["expires_at"],
    )


class _DevicePasswordLoginBody(BaseModel):
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)
    user_code: str = Field(..., min_length=3, max_length=32)


@router.post("/device/login", response_model=MessageResponse)
async def device_login(
    body: _DevicePasswordLoginBody,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    from app.auth.rate_limit import login_account_limiter, login_ip_limiter

    client_ip = request.client.host if request.client else "unknown"
    login_ip_limiter.check(f"device:ip:{client_ip}")
    login_account_limiter.check(f"device:account:{body.email.strip().lower()}")
    auth.login_and_approve_device(
        email=body.email,
        password=body.password,
        user_code=body.user_code,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip,
    )
    return MessageResponse(message="Device approved. You can continue on the other screen.")


@router.post("/device/approve", response_model=MessageResponse)
async def device_approve(
    body: DeviceApproveRequest,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    auth.approve_device_login(
        user_code=body.user_code,
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return MessageResponse(message="Device approved. You can continue on the other screen.")


@router.post("/device/deny", response_model=MessageResponse)
async def device_deny(
    body: DeviceDenyRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    auth.deny_device_login(user_code=body.user_code, user=user)
    return MessageResponse(message="Device login denied.")


def _rp_id_from_request(request: Request, fallback: str) -> str:
    origin = (request.headers.get("origin") or "").strip()
    host = urlparse(origin).hostname if origin else None
    if host:
        return host
    return fallback


@router.post("/passkey/login/options")
async def passkey_login_options(
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    settings = get_settings()
    return auth.passkey_login_options(rp_id=_rp_id_from_request(request, settings.auth_rp_id))


@router.post("/passkey/login/verify", response_model=LoginResponse)
async def passkey_login_verify(
    body: PasskeyVerifyRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    result = auth.passkey_login_verify(
        credential_id=body.credential_id,
        client_data_json=body.client_data_json,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_session_cookie(response, result["session_token"])
    return LoginResponse(
        user=UserPublic(**result["user"]),
        expires_at=result["expires_at"],
    )


@router.post("/passkey/register/options")
async def passkey_register_options(
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    settings = get_settings()
    return auth.passkey_register_options(
        user, rp_id=_rp_id_from_request(request, settings.auth_rp_id)
    )


@router.post("/passkey/register/verify", response_model=MessageResponse)
async def passkey_register_verify(
    body: PasskeyVerifyRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    auth.passkey_register_verify(
        user,
        credential_id=body.credential_id,
        client_data_json=body.client_data_json,
        public_key=body.public_key,
        label=body.label,
    )
    return MessageResponse(message="Passkey registered.")


class _LegalHolderBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    kind: Literal["individual", "sole_proprietor", "company"] = "individual"
    contact: str = Field(default="", max_length=200)
    inn: str = Field(default="", max_length=20)
    country: str = Field(default="RU", min_length=2, max_length=2)


@router.get("/legal")
async def legal_index(
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    settings = get_settings()
    owner = auth.owner_user()
    return {
        "documents": list_documents(settings, owner=owner),
        "holder": load_holder(settings, owner=owner),
    }


@router.put("/legal/holder")
async def update_legal_holder(
    body: _LegalHolderBody,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    if not auth.is_owner(user):
        raise UnauthorizedError()
    try:
        holder = save_holder(get_settings(), body.model_dump(), owner=user)
    except ValueError as exc:
        raise ValidationAuthError(str(exc)) from exc
    return {"ok": True, "holder": holder}


@router.get("/legal/{doc_id}")
async def legal_document(
    doc_id: str,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    try:
        return get_document(get_settings(), doc_id, owner=auth.owner_user())
    except KeyError as exc:
        raise ValidationAuthError("Unknown legal document.") from exc


class _GoogleConfigBody(BaseModel):
    client_id: str = Field(..., min_length=8, max_length=256)
    client_secret: str = Field(..., min_length=8, max_length=256)


@router.post("/oauth/google/config")
async def save_google_oauth_config(
    body: _GoogleConfigBody,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    if not auth.is_owner(user):
        raise UnauthorizedError()
    save_google_oauth(get_settings(), body.client_id, body.client_secret)
    return {"ok": True, "enabled": True}
