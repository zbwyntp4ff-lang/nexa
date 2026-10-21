"""Per-user conversation persistence via shared DATABASE_URL."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.db.engine import Database, get_database


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    title: str = "New chat"
    mode: str = "chat"
    messages_json: str = "[]"
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)


class ConversationStore:
    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def ping(self) -> bool:
        return self._db.ping()

    def migrate(self) -> None:
        self._db.migrate()

    def list_for_user(self, user_id: str, *, limit: int = 50) -> list[ConversationRecord]:
        rows = self._db.fetchall(
            "SELECT id, user_id, title, mode, messages_json, created_at, updated_at "
            "FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [self._row(r) for r in rows]

    def get(self, conversation_id: str, user_id: str) -> ConversationRecord | None:
        row = self._db.fetchone(
            "SELECT id, user_id, title, mode, messages_json, created_at, updated_at "
            "FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        return self._row(row) if row else None

    def upsert(self, record: ConversationRecord) -> ConversationRecord:
        record.updated_at = _utcnow()
        self._db.execute(
            """
            INSERT INTO conversations (id, user_id, title, mode, messages_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              mode = excluded.mode,
              messages_json = excluded.messages_json,
              updated_at = excluded.updated_at
            WHERE conversations.user_id = excluded.user_id
            """,
            (
                record.id,
                record.user_id,
                record.title,
                record.mode,
                record.messages_json,
                record.created_at,
                record.updated_at,
            ),
        )
        return record

    def delete(self, conversation_id: str, user_id: str) -> bool:
        cur = self._db.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        return (cur.rowcount or 0) > 0

    def delete_all_for_user(self, user_id: str) -> int:
        cur = self._db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        return cur.rowcount or 0

    @staticmethod
    def _row(row: Any) -> ConversationRecord:
        if hasattr(row, "keys"):
            data = dict(row)
        else:
            data = {
                "id": row[0],
                "user_id": row[1],
                "title": row[2],
                "mode": row[3],
                "messages_json": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
        return ConversationRecord.model_validate(data)


@lru_cache
def get_conversation_store() -> ConversationStore:
    get_settings()  # ensure settings loaded
    return ConversationStore(get_database())


def encode_messages(messages: list[dict]) -> str:
    return json.dumps(messages, ensure_ascii=False)
