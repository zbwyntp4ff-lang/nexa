"""Authentication HTTP API — register, verify, login, session."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_auth_service
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import get_settings
from app.models.auth_api import (
    AuthStatusResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
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
        email=result["email"],
        sent=bool(result.get("sent")),
        already_verified=bool(result.get("already_verified")),
        code_expires_at=result.get("code_expires_at"),
        resend_available_at=result["resend_available_at"],
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    result = auth.login(
        email=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
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
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MeResponse:
    return MeResponse(user=UserPublic(**auth.public_user(user)))


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    result = auth.request_password_reset(email=body.email)
    return MessageResponse(
        message="If an account exists for that email, a reset code has been sent.",
        email=result.get("email"),
        code_expires_at=result.get("code_expires_at"),
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
