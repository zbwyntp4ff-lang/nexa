"""Auth business logic: register, verify email, login, sessions."""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import timedelta
from typing import Any

from app.auth.documents import DOCUMENT_VERSIONS, REQUIRED_CONSENTS, ConsentDocument
from app.auth.email import EmailService
from app.auth.errors import (
    AccountNotActiveError,
    ConsentRequiredError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidVerificationCodeError,
    PasswordMismatchError,
    RegistrationClosedError,
    SessionInvalidError,
    UnauthorizedError,
    UsernameTakenError,
    ValidationAuthError,
    VerificationAttemptsExceededError,
    VerificationCodeExpiredError,
    VerificationResendCooldownError,
    WeakPasswordError,
)
from app.auth.models import (
    EmailVerificationRecord,
    SessionRecord,
    UserConsent,
    UserRecord,
    utcnow,
)
from app.auth.passwords import (
    generate_numeric_code,
    generate_session_token,
    hash_code,
    hash_password,
    verify_password,
)
from app.auth.store import AuthStore

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
_NAME_RE = re.compile(r"^[\w\s\-'.]{1,64}$", re.UNICODE)


class AuthService:
    def __init__(
        self,
        store: AuthStore,
        email: EmailService,
        *,
        code_ttl_seconds: int = 900,
        resend_cooldown_seconds: int = 60,
        max_verify_attempts: int = 5,
        session_ttl_seconds: int = 60 * 60 * 24 * 14,
        app_name: str = "NEXA",
        owner_emails: set[str] | None = None,
        bootstrap_first_owner: bool = True,
        single_user: bool = True,
        skip_email_verification: bool = True,
    ) -> None:
        self._store = store
        self._email = email
        self._code_ttl = code_ttl_seconds
        self._resend_cooldown = resend_cooldown_seconds
        self._max_attempts = max_verify_attempts
        self._session_ttl = session_ttl_seconds
        self._app_name = app_name
        self._owner_emails = {e.strip().lower() for e in (owner_emails or set()) if e.strip()}
        self._bootstrap_first_owner = bootstrap_first_owner
        self._single_user = single_user
        self._skip_email_verification = skip_email_verification

    def status(self) -> dict[str, Any]:
        users = self._store.list_users()
        has_user = len(users) > 0
        return {
            "single_user": self._single_user,
            "has_user": has_user,
            "registration_open": (not has_user) if self._single_user else True,
            "skip_email_verification": self._skip_email_verification and self._single_user,
        }

    def is_owner(self, user: UserRecord) -> bool:
        if user.is_owner:
            return True
        return user.email.lower() in self._owner_emails

    def _maybe_bootstrap_owner(self, user: UserRecord) -> UserRecord:
        """First verified account becomes owner when no owners exist yet.

        Public/main builds can set AUTH_BOOTSTRAP_FIRST_OWNER=false and/or
        AUTH_OWNER_EMAILS so only your accounts keep the Developer button.
        """
        if not self._bootstrap_first_owner:
            return user
        if self._owner_emails:
            # Explicit allow-list mode: do not auto-promote.
            if user.email.lower() in self._owner_emails and not user.is_owner:
                user.is_owner = True
                user.updated_at = utcnow()
                self._store.save_user(user)
            return user
        if user.is_owner:
            return user
        if self._store.has_owner():
            return user
        user.is_owner = True
        user.updated_at = utcnow()
        self._store.save_user(user)
        return user

    # --- public API -------------------------------------------------------
    def register(
        self,
        *,
        first_name: str,
        last_name: str,
        username: str,
        email: str,
        password: str,
        confirm_password: str,
        accept_terms: bool,
        accept_privacy: bool,
        accept_license: bool,
    ) -> dict[str, Any]:
        first_name = first_name.strip()
        last_name = last_name.strip()
        username = username.strip()
        email = email.strip().lower()

        self._validate_profile(first_name, last_name, username, email)
        if password != confirm_password:
            raise PasswordMismatchError()
        self._validate_password(password)
        if not (accept_terms and accept_privacy and accept_license):
            raise ConsentRequiredError()

        if self._store.get_user_by_email(email):
            raise EmailAlreadyRegisteredError()
        if self._store.get_user_by_username(username):
            raise UsernameTakenError()
        if self._single_user and self._store.list_users():
            raise RegistrationClosedError()

        now = utcnow()
        consents: list[UserConsent] = []
        accepted_flags: dict[ConsentDocument, bool] = {
            "terms_of_service": accept_terms,
            "privacy_policy": accept_privacy,
            "license_agreement": accept_license,
        }
        for doc in REQUIRED_CONSENTS:
            if not accepted_flags[doc]:
                raise ConsentRequiredError()
            consents.append(
                UserConsent(document=doc, version=DOCUMENT_VERSIONS[doc], accepted_at=now)
            )

        auto_verify = self._single_user and self._skip_email_verification
        user = UserRecord(
            id=str(uuid.uuid4()),
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password_hash=hash_password(password),
            email_verified=auto_verify,
            is_active=auto_verify,
            is_owner=False,
            consents=consents,
            created_at=now,
            updated_at=now,
        )
        self._store.save_user(user)
        if auto_verify:
            user = self._maybe_bootstrap_owner(user)
            return {
                "user": self.public_user(user),
                "email": user.email,
                "verification_id": "",
                "code_expires_at": now.isoformat(),
                "resend_available_at": now.isoformat(),
                "ready": True,
            }

        verification = self._issue_verification(user, purpose="email_verification", force=True)
        return {
            "user": self.public_user(user),
            "verification_id": verification.id,
            "email": user.email,
            "code_expires_at": verification.expires_at.isoformat(),
            "resend_available_at": (
                verification.last_sent_at + timedelta(seconds=self._resend_cooldown)
            ).isoformat(),
            "ready": False,
        }

    def verify_email(self, *, email: str, code: str) -> dict[str, Any]:
        email = email.strip().lower()
        code = code.strip()
        user = self._store.get_user_by_email(email)
        if not user:
            raise InvalidVerificationCodeError()
        record = self._active_verification(user.id, purpose="email_verification")
        self._consume_code(record, code)

        now = utcnow()
        user.email_verified = True
        user.is_active = True
        user.updated_at = now
        self._store.save_user(user)
        user = self._maybe_bootstrap_owner(user)
        return {"user": self.public_user(user)}

    def resend_verification(self, *, email: str) -> dict[str, Any]:
        email = email.strip().lower()
        user = self._store.get_user_by_email(email)
        if not user:
            # Do not leak whether the email exists.
            return {
                "email": email,
                "sent": True,
                "resend_available_at": (utcnow() + timedelta(seconds=self._resend_cooldown)).isoformat(),
            }
        if user.email_verified and user.is_active:
            return {
                "email": email,
                "sent": False,
                "already_verified": True,
                "resend_available_at": utcnow().isoformat(),
            }
        verification = self._issue_verification(user, purpose="email_verification", force=False)
        return {
            "email": user.email,
            "verification_id": verification.id,
            "sent": True,
            "code_expires_at": verification.expires_at.isoformat(),
            "resend_available_at": (
                verification.last_sent_at + timedelta(seconds=self._resend_cooldown)
            ).isoformat(),
        }

    def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        email = email.strip().lower()
        user = self._store.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        if not user.email_verified:
            raise EmailNotVerifiedError()
        if not user.is_active:
            raise AccountNotActiveError()

        user = self._maybe_bootstrap_owner(user)
        raw_token, session = self._create_session(user, user_agent=user_agent, ip_address=ip_address)
        return {
            "user": self.public_user(user),
            "session_token": raw_token,
            "expires_at": session.expires_at.isoformat(),
        }

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        session = self._store.get_session_by_token_hash(self._token_hash(raw_token))
        if session and session.revoked_at is None:
            self._store.revoke_session(session.id)

    def get_user_for_token(self, raw_token: str | None) -> UserRecord:
        if not raw_token:
            raise UnauthorizedError()
        session = self._store.get_session_by_token_hash(self._token_hash(raw_token))
        if not session or session.revoked_at is not None:
            raise SessionInvalidError()
        if session.expires_at <= utcnow():
            raise SessionInvalidError()
        user = self._store.get_user(session.user_id)
        if not user or not user.is_active or not user.email_verified:
            raise SessionInvalidError()
        return self._maybe_bootstrap_owner(user)

    def request_password_reset(self, *, email: str) -> dict[str, Any]:
        email = email.strip().lower()
        user = self._store.get_user_by_email(email)
        # Always return the same shape to avoid account enumeration.
        fake_at = (utcnow() + timedelta(seconds=self._resend_cooldown)).isoformat()
        if not user:
            return {"email": email, "sent": True, "resend_available_at": fake_at}
        verification = self._issue_verification(user, purpose="password_reset", force=False)
        return {
            "email": user.email,
            "sent": True,
            "code_expires_at": verification.expires_at.isoformat(),
            "resend_available_at": (
                verification.last_sent_at + timedelta(seconds=self._resend_cooldown)
            ).isoformat(),
        }

    def reset_password(
        self, *, email: str, code: str, password: str, confirm_password: str
    ) -> dict[str, Any]:
        email = email.strip().lower()
        if password != confirm_password:
            raise PasswordMismatchError()
        self._validate_password(password)
        user = self._store.get_user_by_email(email)
        if not user:
            raise InvalidVerificationCodeError()
        record = self._active_verification(user.id, purpose="password_reset")
        self._consume_code(record, code.strip())
        user.password_hash = hash_password(password)
        user.updated_at = utcnow()
        self._store.save_user(user)
        return {"ok": True}

    def public_user(self, user: UserRecord) -> dict[str, Any]:
        return {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "email_verified": user.email_verified,
            "is_active": user.is_active,
            "is_owner": self.is_owner(user),
            "consents": [
                {
                    "document": c.document,
                    "version": c.version,
                    "accepted_at": c.accepted_at.isoformat(),
                }
                for c in user.consents
            ],
            "created_at": user.created_at.isoformat(),
        }

    # --- internals --------------------------------------------------------
    def _validate_profile(self, first_name: str, last_name: str, username: str, email: str) -> None:
        if not _NAME_RE.match(first_name) or not _NAME_RE.match(last_name):
            raise ValidationAuthError("First and last name are required.")
        if not _USERNAME_RE.match(username):
            raise ValidationAuthError(
                "Username must be 3–32 characters: letters, numbers, underscore."
            )
        if not _EMAIL_RE.match(email):
            raise ValidationAuthError("Enter a valid email address.")

    def _validate_password(self, password: str) -> None:
        if len(password) < 8 or len(password) > 128:
            raise WeakPasswordError("Password must be between 8 and 128 characters.")
        if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise WeakPasswordError("Password must include at least one letter and one number.")

    def _issue_verification(
        self, user: UserRecord, *, purpose: str, force: bool
    ) -> EmailVerificationRecord:
        existing = self._store.list_verifications_for_user(user.id, purpose=purpose)
        now = utcnow()
        for old in existing:
            if old.used_at is None and old.expires_at > now:
                elapsed = (now - old.last_sent_at).total_seconds()
                if not force and elapsed < self._resend_cooldown:
                    raise VerificationResendCooldownError(
                        int(self._resend_cooldown - elapsed) + 1
                    )
                # Invalidate unused prior codes when issuing a new one.
                old.used_at = now
                self._store.save_verification(old)

        code = generate_numeric_code(6)
        record = EmailVerificationRecord(
            id=str(uuid.uuid4()),
            user_id=user.id,
            email=user.email,
            code_hash=hash_code(code),
            purpose=purpose,  # type: ignore[arg-type]
            attempts=0,
            max_attempts=self._max_attempts,
            created_at=now,
            expires_at=now + timedelta(seconds=self._code_ttl),
            used_at=None,
            last_sent_at=now,
        )
        self._store.save_verification(record)
        self._send_code_email(user.email, code, purpose=purpose, expires_minutes=self._code_ttl // 60)
        return record

    def _active_verification(self, user_id: str, *, purpose: str) -> EmailVerificationRecord:
        now = utcnow()
        for record in self._store.list_verifications_for_user(user_id, purpose=purpose):
            if record.used_at is not None:
                continue
            if record.expires_at <= now:
                continue
            return record
        raise VerificationCodeExpiredError()

    def _consume_code(self, record: EmailVerificationRecord, code: str) -> None:
        now = utcnow()
        if record.used_at is not None:
            raise InvalidVerificationCodeError()
        if record.expires_at <= now:
            raise VerificationCodeExpiredError()
        if record.attempts >= record.max_attempts:
            raise VerificationAttemptsExceededError()

        record.attempts += 1
        if hash_code(code) != record.code_hash:
            self._store.save_verification(record)
            if record.attempts >= record.max_attempts:
                raise VerificationAttemptsExceededError()
            raise InvalidVerificationCodeError()

        record.used_at = now
        self._store.save_verification(record)

    def _create_session(
        self,
        user: UserRecord,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[str, SessionRecord]:
        raw = generate_session_token()
        now = utcnow()
        session = SessionRecord(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=self._token_hash(raw),
            created_at=now,
            expires_at=now + timedelta(seconds=self._session_ttl),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self._store.save_session(session)
        return raw, session

    @staticmethod
    def _token_hash(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _send_code_email(self, email: str, code: str, *, purpose: str, expires_minutes: int) -> None:
        if purpose == "password_reset":
            subject = f"{self._app_name} password reset code"
            text = (
                f"Your {self._app_name} password reset code is: {code}\n\n"
                f"This code expires in {expires_minutes} minutes. "
                "If you did not request a reset, ignore this email."
            )
        else:
            subject = f"{self._app_name} email verification code"
            text = (
                f"Your {self._app_name} verification code is: {code}\n\n"
                f"This code expires in {expires_minutes} minutes. "
                "If you did not create an account, ignore this email."
            )
        self._email.send(to=email, subject=subject, text_body=text)
