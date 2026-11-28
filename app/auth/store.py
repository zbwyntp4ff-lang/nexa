"""JSON-file persistence for auth entities (matches LocalMemoryStore style)."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from app.auth.models import (
    DeviceLoginRecord,
    EmailVerificationRecord,
    OAuthStateRecord,
    PasskeyChallengeRecord,
    SessionRecord,
    UserRecord,
)


class AuthStore:
    """Thread-safe JSON store for users, verification codes, and sessions."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._users: dict[str, UserRecord] = {}
        self._by_email: dict[str, str] = {}
        self._by_username: dict[str, str] = {}
        self._by_oauth: dict[str, str] = {}  # "provider:subject" -> user_id
        self._verifications: dict[str, EmailVerificationRecord] = {}
        self._sessions: dict[str, SessionRecord] = {}
        self._devices: dict[str, DeviceLoginRecord] = {}
        self._oauth_states: dict[str, OAuthStateRecord] = {}
        self._passkey_challenges: dict[str, PasskeyChallengeRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # Never silently treat an unreadable/corrupt account database as
            # an empty store: that makes every existing login look invalid
            # and can overwrite the only copy on the next account write.
            raise RuntimeError(
                f"Cannot load NEXA auth store at {self._path}: {exc}"
            ) from exc
        dirty = False
        for entry in raw.get("users", []):
            user = UserRecord.model_validate(entry)
            # Repair emails corrupted by paste artifacts (e.g. leading "•").
            from app.auth.service import normalize_email

            cleaned = normalize_email(user.email)
            if cleaned and cleaned != user.email:
                user.email = cleaned
                dirty = True
            self._users[user.id] = user
            self._by_email[user.email.lower()] = user.id
            self._by_username[user.username.lower()] = user.id
            if user.oauth_provider and user.oauth_subject:
                self._by_oauth[f"{user.oauth_provider}:{user.oauth_subject}"] = user.id
        for entry in raw.get("verifications", []):
            item = EmailVerificationRecord.model_validate(entry)
            self._verifications[item.id] = item
        for entry in raw.get("sessions", []):
            item = SessionRecord.model_validate(entry)
            self._sessions[item.id] = item
        legacy_device_tokens = False
        for entry in raw.get("devices", []):
            item = DeviceLoginRecord.model_validate(entry)
            if item.session_token:
                # An approved device login cannot survive a server restart:
                # discard legacy plaintext bearer tokens from disk.
                legacy_device_tokens = True
                continue
            self._devices[item.device_code] = item
        for entry in raw.get("oauth_states", []):
            item = OAuthStateRecord.model_validate(entry)
            self._oauth_states[item.state] = item
        for entry in raw.get("passkey_challenges", []):
            item = PasskeyChallengeRecord.model_validate(entry)
            self._passkey_challenges[item.challenge] = item
        if dirty or legacy_device_tokens:
            self._flush()

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [u.model_dump(mode="json") for u in self._users.values()],
            "verifications": [v.model_dump(mode="json") for v in self._verifications.values()],
            "sessions": [s.model_dump(mode="json") for s in self._sessions.values()],
            "devices": [d.model_dump(mode="json") for d in self._devices.values()],
            "oauth_states": [s.model_dump(mode="json") for s in self._oauth_states.values()],
            "passkey_challenges": [
                c.model_dump(mode="json") for c in self._passkey_challenges.values()
            ],
        }
        encoded = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.", suffix=".tmp", dir=self._path.parent
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    # --- users ------------------------------------------------------------
    def create_user_if_available(
        self, user: UserRecord, *, single_user: bool = False
    ) -> str | None:
        """Atomically reserve a unique email/username and persist a new user.

        Returns email, username, or registration_closed on conflict; returns
        None after a successful insert. Check and insert share one lock.
        """
        with self._lock:
            if user.email.lower() in self._by_email:
                return "email"
            if user.username.lower() in self._by_username:
                return "username"
            if single_user and self._users:
                return "registration_closed"
            self._users[user.id] = user
            self._by_email[user.email.lower()] = user.id
            self._by_username[user.username.lower()] = user.id
            if user.oauth_provider and user.oauth_subject:
                self._by_oauth[f"{user.oauth_provider}:{user.oauth_subject}"] = user.id
            self._flush()
            return None

    def save_user(self, user: UserRecord) -> UserRecord:
        with self._lock:
            self._users[user.id] = user
            self._by_email[user.email.lower()] = user.id
            self._by_username[user.username.lower()] = user.id
            if user.oauth_provider and user.oauth_subject:
                self._by_oauth[f"{user.oauth_provider}:{user.oauth_subject}"] = user.id
            self._flush()
        return user

    def delete_user(self, user_id: str) -> bool:
        """Remove the user and related auth artifacts (sessions already revoked separately)."""
        with self._lock:
            user = self._users.pop(user_id, None)
            if user is None:
                return False
            self._by_email.pop(user.email.lower(), None)
            self._by_username.pop(user.username.lower(), None)
            if user.oauth_provider and user.oauth_subject:
                self._by_oauth.pop(f"{user.oauth_provider}:{user.oauth_subject}", None)
            self._verifications = {
                vid: v for vid, v in self._verifications.items() if v.user_id != user_id
            }
            self._sessions = {
                sid: s for sid, s in self._sessions.items() if s.user_id != user_id
            }
            self._devices = {
                code: d for code, d in self._devices.items() if d.user_id != user_id
            }
            self._passkey_challenges = {
                challenge: item
                for challenge, item in self._passkey_challenges.items()
                if item.user_id != user_id
            }
            self._flush()
            return True

    def get_user_by_oauth(self, provider: str, subject: str) -> UserRecord | None:
        with self._lock:
            uid = self._by_oauth.get(f"{provider}:{subject}")
            return self._users.get(uid) if uid else None

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> UserRecord | None:
        with self._lock:
            uid = self._by_email.get(email.strip().lower())
            return self._users.get(uid) if uid else None

    def get_user_by_username(self, username: str) -> UserRecord | None:
        with self._lock:
            uid = self._by_username.get(username.strip().lower())
            return self._users.get(uid) if uid else None

    def list_users(self) -> list[UserRecord]:
        with self._lock:
            return list(self._users.values())

    def has_owner(self) -> bool:
        with self._lock:
            return any(u.is_owner for u in self._users.values())

    # --- verifications ----------------------------------------------------
    def save_verification(self, record: EmailVerificationRecord) -> EmailVerificationRecord:
        with self._lock:
            self._verifications[record.id] = record
            self._flush()
        return record

    def get_verification(self, verification_id: str) -> EmailVerificationRecord | None:
        with self._lock:
            return self._verifications.get(verification_id)

    def list_verifications_for_user(
        self, user_id: str, *, purpose: str | None = None
    ) -> list[EmailVerificationRecord]:
        with self._lock:
            items = [v for v in self._verifications.values() if v.user_id == user_id]
        if purpose:
            items = [v for v in items if v.purpose == purpose]
        return sorted(items, key=lambda v: v.created_at, reverse=True)

    # --- sessions ---------------------------------------------------------
    def save_session(self, session: SessionRecord) -> SessionRecord:
        with self._lock:
            self._sessions[session.id] = session
            self._flush()
        return session

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_session_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        with self._lock:
            for session in self._sessions.values():
                if session.token_hash == token_hash:
                    return session
        return None

    def revoke_session(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            from app.auth.models import utcnow

            session.revoked_at = utcnow()
            self._sessions[session_id] = session
            self._flush()

    def revoke_all_sessions_for_user(self, user_id: str) -> int:
        with self._lock:
            from app.auth.models import utcnow

            now = utcnow()
            count = 0
            for session in self._sessions.values():
                if session.user_id == user_id and session.revoked_at is None:
                    session.revoked_at = now
                    count += 1
            if count:
                self._flush()
            return count

    # --- device login -----------------------------------------------------
    def save_device(self, record: DeviceLoginRecord) -> DeviceLoginRecord:
        with self._lock:
            self._devices[record.device_code] = record
            self._flush()
        return record

    def get_device(self, device_code: str) -> DeviceLoginRecord | None:
        with self._lock:
            return self._devices.get(device_code)

    def get_device_by_user_code(self, user_code: str) -> DeviceLoginRecord | None:
        code = user_code.strip().upper().replace(" ", "")
        with self._lock:
            for item in self._devices.values():
                if item.user_code.replace("-", "") == code.replace("-", ""):
                    return item
        return None

    # --- oauth state ------------------------------------------------------
    def save_oauth_state(self, record: OAuthStateRecord) -> OAuthStateRecord:
        with self._lock:
            self._oauth_states[record.state] = record
            self._flush()
        return record

    def pop_oauth_state(self, state: str) -> OAuthStateRecord | None:
        with self._lock:
            item = self._oauth_states.pop(state, None)
            if item:
                self._flush()
            return item

    # --- passkey challenges -----------------------------------------------
    def save_passkey_challenge(self, record: PasskeyChallengeRecord) -> PasskeyChallengeRecord:
        with self._lock:
            self._passkey_challenges[record.challenge] = record
            self._flush()
        return record

    def pop_passkey_challenge(self, challenge: str) -> PasskeyChallengeRecord | None:
        with self._lock:
            item = self._passkey_challenges.pop(challenge, None)
            if item:
                self._flush()
            return item

    def find_user_by_passkey(self, credential_id: str) -> UserRecord | None:
        with self._lock:
            for user in self._users.values():
                for pk in user.passkeys:
                    if pk.credential_id == credential_id:
                        return user
        return None
