"""Lightweight SQL engine used by conversations + memory (stdlib sqlite3 / optional psycopg)."""
from __future__ import annotations

import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root


class Database:
    def __init__(self, database_url: str) -> None:
        self._url = database_url.strip()
        self._pg = self._url.startswith("postgres")
        self._lock = threading.RLock()
        self._conn: Any = None
        self._connect()
        self.migrate()

    @property
    def is_postgres(self) -> bool:
        return self._pg

    def _connect(self) -> None:
        if self._pg:
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "DATABASE_URL is PostgreSQL but psycopg is not installed."
                ) from exc
            self._conn = psycopg.connect(self._url, autocommit=True)
            return
        path = self._sqlite_path(self._url)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    @staticmethod
    def _sqlite_path(url: str) -> Path:
        if url.startswith("sqlite:///"):
            raw = url[len("sqlite:///") :]
        elif url.startswith("sqlite://"):
            raw = url[len("sqlite://") :]
        else:
            raw = "data/nexa.db"
        return resolve_under_project_root(raw) if not Path(raw).is_absolute() else Path(raw)

    def migrate(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            mode TEXT NOT NULL,
            messages_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations (user_id, updated_at DESC);
        CREATE TABLE IF NOT EXISTS guest_usage (
            client_key TEXT PRIMARY KEY,
            day_key TEXT NOT NULL,
            daily_count INTEGER NOT NULL,
            hour_window_start REAL NOT NULL,
            hour_count INTEGER NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_items (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_user
            ON memory_items (user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_memory_type
            ON memory_items (type);
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            record_json TEXT NOT NULL,
            text_content TEXT,
            chunks_json TEXT NOT NULL,
            storage_filename TEXT,
            expires_at DOUBLE PRECISION
        );
        CREATE INDEX IF NOT EXISTS idx_attachments_user
            ON attachments (user_id, expires_at);
        CREATE INDEX IF NOT EXISTS idx_attachments_expiry
            ON attachments (expires_at);
        CREATE TABLE IF NOT EXISTS video_jobs (
            job_id TEXT PRIMARY KEY,
            user_id TEXT,
            status_json TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_video_jobs_user
            ON video_jobs (user_id, updated_at DESC);
        """
        with self._lock:
            if self._pg:
                with self._conn.cursor() as cur:
                    for stmt in ddl.split(";"):
                        s = stmt.strip()
                        if s:
                            cur.execute(s)
            else:
                self._conn.executescript(ddl)
                self._conn.commit()

    def ping(self) -> bool:
        with self._lock:
            cur = self._conn.execute("SELECT 1")
            cur.fetchone()
            return True

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        """Run a statement. Callers must hold semantics; sqlite commits inside."""
        with self._lock:
            if self._pg:
                sql = sql.replace("?", "%s")
            cur = self._conn.execute(sql, params)
            if not self._pg:
                self._conn.commit()
            return cur

    def executemany(self, sql: str, seq: list) -> None:
        with self._lock:
            if self._pg:
                sql = sql.replace("?", "%s")
            self._conn.executemany(sql, seq)
            if not self._pg:
                self._conn.commit()

    def fetchall(self, sql: str, params: tuple | list = ()) -> list:
        cur = self.execute(sql, params)
        return list(cur.fetchall())

    def fetchone(self, sql: str, params: tuple | list = ()) -> Any:
        cur = self.execute(sql, params)
        return cur.fetchone()


@lru_cache
def get_database() -> Database:
    settings = get_settings()
    url = (settings.database_url or "sqlite:///data/nexa.db").strip()
    return Database(url)
