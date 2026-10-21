"""Auth domain models persisted by :mod:`app.auth.store`."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.auth.documents import ConsentDocument


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserConsent(BaseModel):
    document: ConsentDocument
    version: str
    accepted_at: datetime


class PasskeyCredential(BaseModel):
    credential_id: str
    public_key: str
    sign_count: int = 0
    label: str = "Passkey"
    created_at: datetime = Field(default_factory=utcnow)


class UserRecord(BaseModel):
    id: str
    first_name: str
    last_name: str
    username: str
    email: str
    password_hash: str
    email_verified: bool = False
    is_active: bool = False
    is_owner: bool = False
    oauth_provider: str | None = None
    oauth_subject: str | None = None
    passkeys: list[PasskeyCredential] = Field(default_factory=list)
    consents: list[UserConsent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DeviceLoginRecord(BaseModel):
    """Desktop/device login approval (QR / user_code)."""

    device_code: str
    user_code: str
    status: Literal["pending", "approved", "expired", "denied"] = "pending"
    user_id: str | None = None
    session_token: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    approved_at: datetime | None = None


class OAuthStateRecord(BaseModel):
    state: str
    provider: str
    redirect_uri: str
    return_origin: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class PasskeyChallengeRecord(BaseModel):
    challenge: str
    purpose: Literal["login", "register"] = "login"
    user_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class EmailVerificationRecord(BaseModel):
    id: str
    user_id: str
    email: str
    code_hash: str
    purpose: Literal["email_verification", "password_reset"] = "email_verification"
    attempts: int = 0
    max_attempts: int = 5
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = None
    last_sent_at: datetime = Field(default_factory=utcnow)


class SessionRecord(BaseModel):
    id: str
    user_id: str
    token_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None
