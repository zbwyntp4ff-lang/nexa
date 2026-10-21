"""HTTP request/response models for auth endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=64)
    last_name: str = Field(..., min_length=1, max_length=64)
    username: str = Field(..., min_length=3, max_length=32)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    accept_terms: bool
    accept_privacy: bool
    accept_license: bool


class VerifyEmailRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    code: str = Field(..., min_length=6, max_length=6)


class ResendCodeRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class ConsentPublic(BaseModel):
    document: str
    version: str
    accepted_at: str


class UserPublic(BaseModel):
    id: str
    first_name: str
    last_name: str
    username: str
    email: str
    email_verified: bool
    is_active: bool
    is_owner: bool = False
    consents: list[ConsentPublic] = Field(default_factory=list)
    created_at: str


class RegisterResponse(BaseModel):
    user: UserPublic
    email: str
    verification_id: str
    code_expires_at: str
    resend_available_at: str
    ready: bool = False
    message: str = "Account created. Verify your email to activate it."
    # Returned for desktop/Electron where cookie may not stick across localhost vs 127.0.0.1.
    session_token: str | None = None


class AuthStatusResponse(BaseModel):
    single_user: bool
    has_user: bool
    registration_open: bool
    skip_email_verification: bool


class VerifyEmailResponse(BaseModel):
    user: UserPublic
    message: str = "Email verified. Your account is now active."


class ResendCodeResponse(BaseModel):
    email: str
    sent: bool
    already_verified: bool = False
    code_expires_at: str | None = None
    resend_available_at: str
    message: str = "If an account exists, a new code has been sent."


class LoginResponse(BaseModel):
    user: UserPublic
    expires_at: str
    message: str = "Signed in."
    # Returned for desktop/Electron where cookie may not stick across localhost vs 127.0.0.1.
    session_token: str | None = None


class MeResponse(BaseModel):
    user: UserPublic


class MessageResponse(BaseModel):
    message: str
    email: str | None = None
    code_expires_at: str | None = None
    resend_available_at: str | None = None


class ProviderInfo(BaseModel):
    id: str
    label: str
    enabled: bool
    kind: str


class ProvidersResponse(BaseModel):
    oauth: list[ProviderInfo]
    device: ProviderInfo
    passkey: ProviderInfo
    password: ProviderInfo


class OAuthStartResponse(BaseModel):
    authorize_url: str
    state: str
    provider: str


class DeviceStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int
    qr_payload: str
    qr_svg: str = ""
    phone_url: str = ""


class DeviceApproveRequest(BaseModel):
    user_code: str = Field(..., min_length=3, max_length=32)


class DeviceDenyRequest(BaseModel):
    user_code: str = Field(..., min_length=3, max_length=32)


class PasskeyVerifyRequest(BaseModel):
    credential_id: str = Field(..., min_length=8, max_length=512)
    client_data_json: str = Field(..., min_length=8)
    public_key: str = ""
    label: str = "Passkey"


class DeleteAccountRequest(BaseModel):
    """Server-side confirmation for irreversible account wipe."""

    confirm: str = Field(..., min_length=1, max_length=32)
