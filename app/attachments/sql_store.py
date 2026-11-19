"""SQL persistence for attachment metadata and extracted document text."""
from __future__ import annotations

import json
from typing import Any

from app.attachments.models import AttachmentRecord
from app.db.engine import Database


class SqlAttachmentStore:
    """Durable attachment metadata/content store; raw image bytes remain on disk."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(
        self,
        record: AttachmentRecord,
        *,
        text: str | None,
        chunks: list[str],
        storage_filename: str | None,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO attachments
              (id, user_id, record_json, text_content, chunks_json, storage_filename, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              user_id = excluded.user_id,
              record_json = excluded.record_json,
              text_content = excluded.text_content,
              chunks_json = excluded.chunks_json,
              storage_filename = excluded.storage_filename,
              expires_at = excluded.expires_at
            WHERE attachments.user_id = excluded.user_id OR (attachments.user_id IS NULL AND excluded.user_id IS NULL)
            """,
            (
                record.id,
                record.user_id,
                record.model_dump_json(),
                text,
                json.dumps(chunks, ensure_ascii=False),
                storage_filename,
                record.expires_at.timestamp() if record.expires_at else None,
            ),
        )

    def get(self, attachment_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        sql = (
            "SELECT id, user_id, record_json, text_content, chunks_json, storage_filename "
            "FROM attachments WHERE id = ?"
        )
        params: tuple = (attachment_id,)
        if user_id is not None:
            sql += " AND user_id = ?"
            params = (attachment_id, user_id)
        row = self._db.fetchone(sql, params)
        return self._decode(row) if row else None

    def list(self, user_id: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT id, user_id, record_json, text_content, chunks_json, storage_filename "
            "FROM attachments"
        )
        params: tuple = ()
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params = (user_id,)
        sql += " ORDER BY id"
        return [self._decode(row) for row in self._db.fetchall(sql, params)]

    def expired_ids(self, now: float) -> list[str]:
        rows = self._db.fetchall(
            "SELECT id FROM attachments WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        return [str(row["id"] if hasattr(row, "keys") else row[0]) for row in rows]

    def delete(self, attachment_id: str, user_id: str | None = None) -> bool:
        sql = "DELETE FROM attachments WHERE id = ?"
        params: tuple = (attachment_id,)
        if user_id is not None:
            sql += " AND user_id = ?"
            params = (attachment_id, user_id)
        cur = self._db.execute(sql, params)
        return (cur.rowcount or 0) > 0

    def delete_user(self, user_id: str) -> int:
        cur = self._db.execute("DELETE FROM attachments WHERE user_id = ?", (user_id,))
        return cur.rowcount or 0

    @staticmethod
    def _decode(row: Any) -> dict[str, Any]:
        if hasattr(row, "keys"):
            data = dict(row)
        else:
            data = dict(zip(
                ("id", "user_id", "record_json", "text_content", "chunks_json", "storage_filename"),
                row,
            ))
        return {
            "record": AttachmentRecord.model_validate_json(data["record_json"]),
            "text": data["text_content"],
            "chunks": json.loads(data["chunks_json"] or "[]"),
            "storage_filename": data["storage_filename"],
        }
