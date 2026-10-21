"""SQL-backed MemoryStore — durable multi-user persistence via DATABASE_URL."""
from __future__ import annotations

import json
from datetime import datetime

from app.db.engine import Database, get_database
from app.memory.models import MemoryItem, MemorySearchResult, MemoryType
from app.memory.store import MemoryStore


class SqlMemoryStore(MemoryStore):
    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def save(self, item: MemoryItem) -> MemoryItem:
        self._db.execute(
            """
            INSERT INTO memory_items
              (id, user_id, type, content, tags_json, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              user_id = excluded.user_id,
              type = excluded.type,
              content = excluded.content,
              tags_json = excluded.tags_json,
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                item.id,
                item.user_id,
                item.type.value if isinstance(item.type, MemoryType) else str(item.type),
                item.content,
                json.dumps(item.tags, ensure_ascii=False),
                json.dumps(item.metadata, ensure_ascii=False),
                item.created_at.isoformat()
                if isinstance(item.created_at, datetime)
                else str(item.created_at),
                item.updated_at.isoformat()
                if isinstance(item.updated_at, datetime)
                else str(item.updated_at),
            ),
        )
        return item

    def get(self, item_id: str) -> MemoryItem | None:
        row = self._db.fetchone(
            "SELECT id, user_id, type, content, tags_json, metadata_json, created_at, updated_at "
            "FROM memory_items WHERE id = ?",
            (item_id,),
        )
        return self._row(row) if row else None

    def search(
        self,
        query: str = "",
        type: MemoryType | None = None,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        sql = (
            "SELECT id, user_id, type, content, tags_json, metadata_json, created_at, updated_at "
            "FROM memory_items WHERE 1=1"
        )
        params: list = []
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        if type is not None:
            sql += " AND type = ?"
            params.append(type.value)
        rows = self._db.fetchall(sql, params)
        items = [self._row(r) for r in rows if r]
        query = (query or "").strip().lower()
        if not query:
            scored = [MemorySearchResult(item=i, score=1.0) for i in items]
        else:
            terms = query.split()
            scored = []
            for item in items:
                haystack = f"{item.content} {' '.join(item.tags)}".lower()
                hits = sum(haystack.count(term) for term in terms)
                if hits > 0:
                    scored.append(MemorySearchResult(item=item, score=float(hits)))
        scored.sort(key=lambda r: (r.score, r.item.updated_at), reverse=True)
        return scored[: max(limit, 0)]

    def delete(self, item_id: str) -> bool:
        cur = self._db.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
        return (cur.rowcount or 0) > 0

    def clear(self, type: MemoryType | None = None) -> int:
        if type is None:
            cur = self._db.execute("DELETE FROM memory_items")
        else:
            cur = self._db.execute("DELETE FROM memory_items WHERE type = ?", (type.value,))
        return cur.rowcount or 0

    def clear_user(self, user_id: str, type: MemoryType | None = None) -> int:
        if type is None:
            cur = self._db.execute("DELETE FROM memory_items WHERE user_id = ?", (user_id,))
        else:
            cur = self._db.execute(
                "DELETE FROM memory_items WHERE user_id = ? AND type = ?",
                (user_id, type.value),
            )
        return cur.rowcount or 0

    @staticmethod
    def _row(row) -> MemoryItem:
        data = dict(row) if hasattr(row, "keys") else {
            "id": row[0],
            "user_id": row[1],
            "type": row[2],
            "content": row[3],
            "tags_json": row[4],
            "metadata_json": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
        return MemoryItem(
            id=data["id"],
            user_id=data["user_id"],
            type=MemoryType(data["type"]),
            content=data["content"],
            tags=json.loads(data["tags_json"] or "[]"),
            metadata=json.loads(data["metadata_json"] or "{}"),
            created_at=datetime.fromisoformat(str(data["created_at"]).replace("Z", "+00:00"))
            if not isinstance(data["created_at"], datetime)
            else data["created_at"],
            updated_at=datetime.fromisoformat(str(data["updated_at"]).replace("Z", "+00:00"))
            if not isinstance(data["updated_at"], datetime)
            else data["updated_at"],
        )
