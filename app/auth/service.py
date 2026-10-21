"""Auth business logic: register, verify email, login, sessions."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import socket
import uuid
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from app.auth.documents import DOCUMENT_VERSIONS, REQUIRED_CONSENTS, ConsentDocument
from app.auth.email import EmailService
from app.auth.errors import (
    AccountNotActiveError,
    ConsentRequiredError,
    DeviceLoginError,
    DeviceLoginPendingError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidVerificationCodeError,
    OAuthStateInvalidError,
    PasskeyError,
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
    DeviceLoginRecord,
    EmailVerificationRecord,
    OAuthStateRecord,
    PasskeyChallengeRecord,
    PasskeyCredential,
    SessionRecord,
    UserConsent,
    UserRecord,
    utcnow,
)
from app.auth.oauth import (
    OAuthProfile,
    ProviderId,
    build_authorize_url,
    exchange_code,
    list_provider_status,
    new_oauth_state,
)
from app.auth.qr import qr_svg as make_qr_svg
from app.auth.passwords import (
    generate_numeric_code,
    generate_session_token,
    hash_code,
    hash_password,
    verify_password,
)
from app.auth.store import AuthStore

# Allow common real-world addresses (plus-tags, multi-level domains, unicode dots).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
_NAME_RE = re.compile(r"^[\w\s\-'.]{1,64}$", re.UNICODE)
_INVISIBLE_RE = re.compile(r"[\u200b-\u200d\uFEFF\u00AD]")


_SKIP_IP_PREFIXES = ("127.", "169.254.", "198.18.", "198.19.")


def _is_usable_lan_ip(ip: str) -> bool:
    if not ip or ip.count(".") != 3:
        return False
    return not ip.startswith(_SKIP_IP_PREFIXES)


def _ipv4s_from_ipconfig() -> list[str]:
    import subprocess

    try:
        raw = subprocess.check_output(["ipconfig"], text=True, encoding="oem", errors="replace")
    except (OSError, subprocess.CalledProcessError):
        return []
    found: list[str] = []
    for match in re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", raw):
        if _is_usable_lan_ip(match) and match not in found:
            found.append(match)
    return found


def _lan_ipv4() -> str | None:
    """Prefer a real Wi-Fi/LAN address (192.168/10), never VPN/benchmark tunnels."""
    candidates: list[str] = []
    candidates.extend(_ipv4s_from_ipconfig())
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if _is_usable_lan_ip(ip) and ip not in candidates:
                candidates.append(ip)
    except OSError:
        pass
    wifi = [ip for ip in candidates if ip.startswith("192.168.")]
    private10 = [ip for ip in candidates if ip.startswith("10.")]
    rest = [ip for ip in candidates if ip not in wifi and ip not in private10]
    ordered = wifi + private10 + rest
    return ordered[0] if ordered else None


def _lan_http_origin(port: int) -> str | None:
    ip = _lan_ipv4()
    if not ip:
        return None
    return f"http://{ip}:{port}"


def normalize_email(value: str) -> str:
    """Strip paste artifacts so login/register accept clipboard emails."""
    email = (value or "").replace("\r", "").replace("\n", "").strip()
    email = _INVISIBLE_RE.sub("", email)
    email = email.strip().strip("'\"<>")
    if email.lower().startswith("mailto:"):
        email = email[7:].strip()
    # Collapse odd Unicode spaces left after strip.
    email = "".join(ch for ch in email if not ch.isspace())
    # Leading bullets / rich-text junk (seen in clipboard and corrupt stores).
    email = re.sub(r"^[^A-Za-z0-9._%+-]+", "", email)
    return email.lower()


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
        public_base_url: str = "http://localhost:4820",
        device_ttl_seconds: int = 600,
        rp_id: str = "localhost",
        rp_name: str = "NEXA",
        oauth_settings: Any | None = None,
        api_public_url: str = "",
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
        self._public_base_url = public_base_url.rstrip("/")
        self._device_ttl = device_ttl_seconds
        self._rp_id = rp_id
        self._rp_name = rp_name
        self._oauth_settings = oauth_settings
        self._api_public_url = (api_public_url or "").rstrip("/")

    def status(self) -> dict[str, Any]:
        users = self._store.list_users()
        has_user = len(users) > 0
        return {
            "single_user": self._single_user,
            "has_user": has_user,
            "registration_open": (not has_user) if self._single_user else True,
            "skip_email_verification": self._skip_email_verification,
        }

    def list_login_providers(self) -> dict[str, Any]:
        oauth = list_provider_status(self._oauth_settings) if self._oauth_settings else [
            {"id": "google", "label": "Google", "enabled": False, "kind": "oauth"},
            {"id": "github", "label": "GitHub", "enabled": False, "kind": "oauth"},
            {"id": "apple", "label": "Apple", "enabled": False, "kind": "oauth"},
        ]
        return {
            "oauth": oauth,
            "device": {"id": "device", "label": "QR / device code", "enabled": True, "kind": "device"},
            # Disabled until cryptographic WebAuthn assertion verification ships.
            "passkey": {"id": "passkey", "label": "Passkey", "enabled": False, "kind": "passkey"},
            "password": {"id": "password", "label": "Email & password", "enabled": True, "kind": "password"},
        }

    def is_owner(self, user: UserRecord) -> bool:
        if user.is_owner:
            return True
        return user.email.lower() in self._owner_emails

    def owner_user(self) -> UserRecord | None:
        for user in self._store.list_users():
            if self.is_owner(user):
                return user
        return None

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
        email = normalize_email(email)

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

        auto_verify = self._skip_email_verification
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
        email = normalize_email(email)
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
        email = normalize_email(email)
        user = self._store.get_user_by_email(email)
        if not user:
            # Do not leak whether the email exists.
            return {
                "email": email,
                "sent": True,
                "resend_available_at": (utcnow() + timedelta(seconds=self._resend_cooldown)).isoformat(),
            }
        if user.email_verified and user.is_active:
            # Same shape as unknown email — do not leak account existence.
            return {
                "email": email,
                "sent": True,
                "resend_available_at": (
                    utcnow() + timedelta(seconds=self._resend_cooldown)
                ).isoformat(),
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
        identifier = (email or "").strip()
        user = self._store.get_user_by_email(normalize_email(identifier))
        if user is None and identifier:
            user = self._store.get_user_by_username(identifier)
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

    # --- OAuth ------------------------------------------------------------
    def start_oauth(self, provider: ProviderId, *, return_origin: str = "") -> dict[str, Any]:
        if not self._oauth_settings:
            raise ValidationAuthError("OAuth is not available.")
        state = new_oauth_state()
        redirect_uri = self._oauth_callback_uri(provider, return_origin)
        now = utcnow()
        self._store.save_oauth_state(
            OAuthStateRecord(
                state=state,
                provider=provider,
                redirect_uri=redirect_uri,
                return_origin=return_origin.strip(),
                created_at=now,
                expires_at=now + timedelta(minutes=15),
            )
        )
        url = build_authorize_url(
            self._oauth_settings, provider, state=state, redirect_uri=redirect_uri
        )
        return {"authorize_url": url, "state": state, "provider": provider}

    def _oauth_callback_uri(self, provider: ProviderId, return_origin: str) -> str:
        api = self._api_public_url
        origin = (return_origin or "").rstrip("/")
        if not api:
            if ":48420" in origin:
                api = "http://127.0.0.1:8420"
            else:
                api = self._public_base_url
        return f"{api}/api/v1/auth/oauth/{provider}/callback"

    def oauth_return_url(self, return_origin: str, fallback: str) -> str:
        origin = (return_origin or "").rstrip("/")
        if origin and self._origin_allowed(origin):
            return origin
        return fallback.rstrip("/")

    def _origin_allowed(self, origin: str) -> bool:
        settings = self._oauth_settings
        allowed = []
        if settings is not None:
            allowed = list(getattr(settings, "cors_allowed_origins", []) or [])
        extra = [
            self._public_base_url,
            "http://localhost:4820",
            "http://127.0.0.1:4820",
            "http://localhost:48420",
            "http://127.0.0.1:48420",
        ]
        return origin.rstrip("/") in {item.rstrip("/") for item in [*allowed, *extra] if item}

    async def finish_oauth(
        self,
        provider: ProviderId,
        *,
        code: str,
        state: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        if not self._oauth_settings:
            raise ValidationAuthError("OAuth is not available.")
        record = self._store.pop_oauth_state(state)
        if not record or record.provider != provider:
            raise OAuthStateInvalidError()
        if record.expires_at <= utcnow():
            raise OAuthStateInvalidError()
        profile = await exchange_code(
            self._oauth_settings,
            provider,
            code=code,
            redirect_uri=record.redirect_uri,
        )
        login = self._login_with_oauth_profile(
            profile, user_agent=user_agent, ip_address=ip_address
        )
        login["return_origin"] = record.return_origin
        return login

    def _login_with_oauth_profile(
        self,
        profile: OAuthProfile,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> dict[str, Any]:
        user = self._store.get_user_by_oauth(profile.provider, profile.subject)
        if not user:
            existing = self._store.get_user_by_email(profile.email)
            if existing:
                # Part 15: never auto-link OAuth to an existing password account
                # by email alone — that enables account takeover via IdP email.
                raise ValidationAuthError(
                    "An account with this email already exists. Sign in with "
                    "email and password first, then link the provider from settings."
                )
            if self._single_user and self._store.list_users():
                raise RegistrationClosedError()
            if not profile.email_verified:
                raise ValidationAuthError(
                    "OAuth provider did not confirm a verified email address."
                )
            user = self._create_oauth_user(profile)
        if not user.is_active:
            raise AccountNotActiveError()
        user = self._maybe_bootstrap_owner(user)
        raw_token, session = self._create_session(
            user, user_agent=user_agent, ip_address=ip_address
        )
        return {
            "user": self.public_user(user),
            "session_token": raw_token,
            "expires_at": session.expires_at.isoformat(),
        }

    def _create_oauth_user(self, profile: OAuthProfile) -> UserRecord:
        now = utcnow()
        username = self._unique_username(profile.username_hint)
        # Unusable random password — OAuth accounts sign in via provider / passkey.
        password_hash = hash_password(secrets.token_urlsafe(32))
        consents = [
            UserConsent(document=doc, version=DOCUMENT_VERSIONS[doc], accepted_at=now)
            for doc in REQUIRED_CONSENTS
        ]
        user = UserRecord(
            id=str(uuid.uuid4()),
            first_name=profile.first_name,
            last_name=profile.last_name,
            username=username,
            email=profile.email,
            password_hash=password_hash,
            email_verified=True,
            is_active=True,
            is_owner=False,
            oauth_provider=profile.provider,
            oauth_subject=profile.subject,
            consents=consents,
            created_at=now,
            updated_at=now,
        )
        return self._store.save_user(user)

    def _unique_username(self, hint: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9_]", "_", hint)[:24] or "user"
        if not self._store.get_user_by_username(base):
            return base
        for _ in range(20):
            candidate = f"{base[:20]}_{secrets.token_hex(2)}"
            if not self._store.get_user_by_username(candidate):
                return candidate
        return f"user_{secrets.token_hex(4)}"

    # --- Device / QR ------------------------------------------------------
    def start_device_login(self, *, ui_origin: str | None = None) -> dict[str, Any]:
        now = utcnow()
        device_code = secrets.token_urlsafe(32)
        user_code = self._format_user_code(secrets.token_hex(3).upper())
        record = DeviceLoginRecord(
            device_code=device_code,
            user_code=user_code,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(seconds=self._device_ttl),
        )
        self._store.save_device(record)
        origin = (ui_origin or self._public_base_url).rstrip("/")
        if not origin.startswith("http"):
            origin = self._public_base_url
        verification_uri = f"{origin}/auth/device"
        verification_uri_complete = f"{verification_uri}?code={user_code}"
        # Phones cannot open localhost. QR always points at this PC's LAN IP
        # and the FastAPI port, which serves /auth/device as a real HTML page.
        phone_origin = _lan_http_origin(self._phone_api_port())
        phone_url = f"{phone_origin}/auth/device?code={user_code}" if phone_origin else ""
        qr_payload = phone_url or verification_uri_complete
        return {
            "device_code": device_code,
            "user_code": user_code,
            "verification_uri": verification_uri,
            "verification_uri_complete": verification_uri_complete,
            "phone_url": phone_url,
            "expires_in": self._device_ttl,
            "interval": 2,
            "qr_payload": qr_payload,
            "qr_svg": make_qr_svg(qr_payload),
        }

    def _phone_api_port(self) -> int:
        for candidate in (self._api_public_url, "http://127.0.0.1:8420"):
            if not candidate:
                continue
            parsed = urlparse(candidate if "://" in candidate else f"http://{candidate}")
            if parsed.port:
                return parsed.port
        return 8420

    def poll_device_login(self, device_code: str) -> dict[str, Any]:
        record = self._store.get_device(device_code)
        if not record:
            raise DeviceLoginError("Unknown device code.")
        if record.expires_at <= utcnow() and record.status == "pending":
            record.status = "expired"
            self._store.save_device(record)
        if record.status == "pending":
            raise DeviceLoginPendingError()
        if record.status == "denied":
            raise DeviceLoginError("Device login was denied.")
        if record.status == "expired":
            raise DeviceLoginError("Device login expired.")
        if record.status != "approved" or not record.session_token or not record.user_id:
            raise DeviceLoginError("Device login is not ready.")
        user = self._store.get_user(record.user_id)
        if not user:
            raise DeviceLoginError("User for device login is missing.")
        # One-shot: clear token from record after poll succeeds
        token = record.session_token
        record.session_token = None
        self._store.save_device(record)
        session = self._store.get_session_by_token_hash(self._token_hash(token))
        expires = session.expires_at.isoformat() if session else utcnow().isoformat()
        return {
            "user": self.public_user(user),
            "session_token": token,
            "expires_at": expires,
        }

    def approve_device_login(
        self,
        *,
        user_code: str,
        user: UserRecord,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        record = self._store.get_device_by_user_code(user_code)
        if not record:
            raise DeviceLoginError("Invalid device code.")
        if record.expires_at <= utcnow():
            record.status = "expired"
            self._store.save_device(record)
            raise DeviceLoginError("Device login expired.")
        if record.status != "pending":
            raise DeviceLoginError("This device code is no longer pending.")
        raw_token, session = self._create_session(
            user, user_agent=user_agent, ip_address=ip_address
        )
        record.status = "approved"
        record.user_id = user.id
        record.session_token = raw_token
        record.approved_at = utcnow()
        self._store.save_device(record)
        return {
            "user_code": record.user_code,
            "status": "approved",
            "expires_at": session.expires_at.isoformat(),
        }

    def login_and_approve_device(
        self,
        *,
        email: str,
        password: str,
        user_code: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        login = self.login(
            email=email, password=password, user_agent=user_agent, ip_address=ip_address
        )
        user = self._store.get_user(login["user"]["id"])
        if not user:
            raise DeviceLoginError("User for device login is missing.")
        self.approve_device_login(
            user_code=user_code, user=user, user_agent=user_agent, ip_address=ip_address
        )
        return {"ok": True, "message": "Device approved."}

    def deny_device_login(self, *, user_code: str, user: UserRecord) -> dict[str, Any]:
        record = self._store.get_device_by_user_code(user_code)
        if not record:
            raise DeviceLoginError("Invalid device code.")
        if record.status == "pending":
            record.status = "denied"
            self._store.save_device(record)
        return {"user_code": record.user_code, "status": record.status}

    @staticmethod
    def _format_user_code(raw: str) -> str:
        compact = re.sub(r"[^A-Z0-9]", "", raw.upper())[:8]
        if len(compact) < 6:
            compact = (compact + secrets.token_hex(4).upper())[:6]
        return f"{compact[:3]}-{compact[3:6]}"

    # --- Passkeys ---------------------------------------------------------
    def passkey_login_options(self, *, rp_id: str | None = None) -> dict[str, Any]:
        # Part 15: do not advertise challenges or credential ids until
        # WebAuthn assertion signatures are verified server-side.
        raise PasskeyError(
            "Passkey login is disabled until cryptographic verification is enabled."
        )

    def passkey_login_verify(
        self,
        *,
        credential_id: str,
        client_data_json: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        raise PasskeyError(
            "Passkey login is disabled until cryptographic verification is enabled."
        )

    def passkey_register_options(self, user: UserRecord, *, rp_id: str | None = None) -> dict[str, Any]:
        challenge = self._new_webauthn_challenge()
        now = utcnow()
        self._store.save_passkey_challenge(
            PasskeyChallengeRecord(
                challenge=challenge,
                purpose="register",
                user_id=user.id,
                created_at=now,
                expires_at=now + timedelta(minutes=5),
            )
        )
        exclude = [{"type": "public-key", "id": pk.credential_id} for pk in user.passkeys]
        effective_rp = (rp_id or self._rp_id).strip() or self._rp_id
        return {
            "challenge": challenge,
            "rp": {"name": self._rp_name, "id": effective_rp},
            "user": {
                "id": base64.urlsafe_b64encode(user.id.encode()).decode().rstrip("="),
                "name": user.email,
                "displayName": f"{user.first_name} {user.last_name}".strip() or user.username,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},
                {"type": "public-key", "alg": -257},
            ],
            "timeout": 120_000,
            "attestation": "none",
            "excludeCredentials": exclude,
            "authenticatorSelection": {
                "residentKey": "preferred",
                "userVerification": "preferred",
            },
        }

    def passkey_register_verify(
        self,
        user: UserRecord,
        *,
        credential_id: str,
        client_data_json: str,
        public_key: str = "",
        label: str = "Passkey",
    ) -> dict[str, Any]:
        challenge = self._extract_challenge(client_data_json)
        record = self._store.pop_passkey_challenge(challenge)
        if (
            not record
            or record.purpose != "register"
            or record.user_id != user.id
            or record.expires_at <= utcnow()
        ):
            raise PasskeyError("Passkey registration challenge is invalid or expired.")
        if self._store.find_user_by_passkey(credential_id):
            raise PasskeyError("This passkey is already registered.")
        user.passkeys.append(
            PasskeyCredential(
                credential_id=credential_id,
                public_key=public_key or credential_id,
                label=(label or "Passkey")[:64],
            )
        )
        user.updated_at = utcnow()
        self._store.save_user(user)
        return {
            "ok": True,
            "passkeys": [
                {"credential_id": p.credential_id, "label": p.label}
                for p in user.passkeys
            ],
        }

    def _new_webauthn_challenge(self) -> str:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    def _extract_challenge(self, client_data_json: str) -> str:
        try:
            raw = client_data_json.strip()
            pad = "=" * (-len(raw) % 4)
            data = json.loads(base64.urlsafe_b64decode(raw + pad))
            challenge = str(data.get("challenge") or "")
            if not challenge:
                raise PasskeyError("Missing challenge in clientDataJSON.")
            return challenge.rstrip("=")
        except (ValueError, json.JSONDecodeError) as exc:
            raise PasskeyError("Invalid clientDataJSON.") from exc

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
        self._touch_session(session)
        return self._maybe_bootstrap_owner(user)

    def _touch_session(self, session: SessionRecord) -> None:
        """Slide ``expires_at`` forward while the user is active (until logout).

        Writes are throttled so busy chat traffic does not rewrite the store
        on every request.
        """
        now = utcnow()
        remaining = (session.expires_at - now).total_seconds()
        # Renew when less than half the TTL remains, or at least hourly drift.
        if remaining > max(self._session_ttl * 0.5, 3600):
            return
        session.expires_at = now + timedelta(seconds=self._session_ttl)
        self._store.save_session(session)

    def request_password_reset(self, *, email: str) -> dict[str, Any]:
        email = normalize_email(email)
        user = self._store.get_user_by_email(email)
        # Always return the same shape to avoid account enumeration.
        fake_at = (utcnow() + timedelta(seconds=self._resend_cooldown)).isoformat()
        if not user:
            return {"email": email, "sent": True, "resend_available_at": fake_at}
        verification = self._issue_verification(user, purpose="password_reset", force=False)
        # Omit code_expires_at from the public path — differing fields enable enumeration.
        return {
            "email": email,
            "sent": True,
            "resend_available_at": (
                verification.last_sent_at + timedelta(seconds=self._resend_cooldown)
            ).isoformat(),
        }

    def reset_password(
        self, *, email: str, code: str, password: str, confirm_password: str
    ) -> dict[str, Any]:
        email = normalize_email(email)
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
        self._store.revoke_all_sessions_for_user(user.id)
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
