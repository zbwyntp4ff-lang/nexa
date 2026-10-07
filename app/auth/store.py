"""JSON-file persistence for auth entities (matches LocalMemoryStore style)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from app.auth.models import EmailVerificationRecord, SessionRecord, UserRecord


class AuthStore:
    """Thread-safe JSON store for users, verification codes, and sessions."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._users: dict[str, UserRecord] = {}
        self._by_email: dict[str, str] = {}
        self._by_username: dict[str, str] = {}
        self._verifications: dict[str, EmailVerificationRecord] = {}
        self._sessions: dict[str, SessionRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for entry in raw.get("users", []):
            user = UserRecord.model_validate(entry)
            self._users[user.id] = user
            self._by_email[user.email.lower()] = user.id
            self._by_username[user.username.lower()] = user.id
        for entry in raw.get("verifications", []):
            item = EmailVerificationRecord.model_validate(entry)
            self._verifications[item.id] = item
        for entry in raw.get("sessions", []):
            item = SessionRecord.model_validate(entry)
            self._sessions[item.id] = item

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [u.model_dump(mode="json") for u in self._users.values()],
            "verifications": [v.model_dump(mode="json") for v in self._verifications.values()],
            "sessions": [s.model_dump(mode="json") for s in self._sessions.values()],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    # --- users ------------------------------------------------------------
    def save_user(self, user: UserRecord) -> UserRecord:
        with self._lock:
            self._users[user.id] = user
            self._by_email[user.email.lower()] = user.id
            self._by_username[user.username.lower()] = user.id
            self._flush()
        return user

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
