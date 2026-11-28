"""Secure store for agent-generated binary results (never expose server paths)."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-а-яА-ЯёЁ ]+")
_MAX_NAME_LEN = 120


@dataclass
class GeneratedFile:
    file_id: str
    filename: str
    media_type: str
    size_bytes: int
    task_id: str
    created_at: str
    user_id: str | None = None
    tool_name: str | None = None
    meta: dict[str, Any] | None = None

    @property
    def download_path(self) -> str:
        """API path clients use — not a filesystem path."""
        return f"/api/v1/results/{self.file_id}/download"


class ResultStore:
    """UUID-keyed files under ``<sandbox>/results/`` with a JSON manifest."""

    def __init__(self, sandbox_root: Path, *, subdirectory: str = "results") -> None:
        self._root = sandbox_root.resolve()
        self._dir = self._root / subdirectory
        self._dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._dir / "manifest.json"
        self._index: dict[str, GeneratedFile] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if not self._manifest_path.exists():
            return
        try:
            raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        for fid, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            try:
                self._index[fid] = GeneratedFile(**entry)
            except TypeError:
                continue

    def _save(self) -> None:
        """Atomically persist the manifest using a unique temporary file."""
        payload = {fid: asdict(rec) for fid, rec in self._index.items()}
        fd, tmp_name = tempfile.mkstemp(
            prefix=".manifest-", suffix=".tmp", dir=self._dir
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self._manifest_path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    @staticmethod
    def sanitize_filename(name: str, *, default: str, extension: str) -> str:
        base = (name or default).strip() or default
        if "." in base:
            stem, ext = base.rsplit(".", 1)
            if ext.lower() == extension.lstrip(".").lower():
                base = stem
        base = _SAFE_NAME.sub("_", base).strip(" ._")[:_MAX_NAME_LEN] or default
        ext = extension if extension.startswith(".") else f".{extension}"
        return f"{base}{ext}"

    def absolute_path(self, file_id: str) -> Path | None:
        """Resolve on-disk path for an indexed file_id.

        Does **not** enforce ownership. Callers that expose content to a user
        must use :meth:`get` with ``user_id`` first (see Results API / open_result).
        """
        with self._lock:
            rec = self._index.get(file_id)
            if rec is None:
                return None
            path = (self._dir / f"{file_id}{Path(rec.filename).suffix}").resolve()
            try:
                path.relative_to(self._dir.resolve())
            except ValueError:
                return None
            return path if path.is_file() else None

    def get(self, file_id: str, *, user_id: str | None = None) -> GeneratedFile | None:
        """Return a result if the caller may access it.

        When ``TOKENS_ENFORCE`` is on (multi-user cloud), ownerless records are
        denied and ``user_id`` must match ``rec.user_id``. Local single-user
        mode still allows legacy ownerless files for desktop convenience.
        """
        with self._lock:
            rec = self._index.get(file_id)
            if rec is None:
                return None
            enforce = False
            try:
                from app.config.settings import get_settings

                enforce = bool(get_settings().tokens_enforce)
            except Exception:  # noqa: BLE001
                enforce = False
            if enforce:
                if not user_id or not rec.user_id or rec.user_id != user_id:
                    return None
            elif user_id is not None and rec.user_id and rec.user_id != user_id:
                return None
            if self.absolute_path(file_id) is None:
                return None
            return copy.deepcopy(rec)

    def save_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        media_type: str,
        extension: str,
        task_id: str,
        tool_name: str | None = None,
        user_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> GeneratedFile:
        if not data:
            raise ValueError("Generated file is empty.")
        with self._lock:
            file_id = uuid.uuid4().hex
            safe_name = self.sanitize_filename(filename, default="document", extension=extension)
            target = self._dir / f"{file_id}{Path(safe_name).suffix}"
            try:
                with target.open("xb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError as exc:
                raise FileExistsError(f"Result path already exists: {file_id}") from exc
            if not target.is_file() or target.stat().st_size <= 0:
                target.unlink(missing_ok=True)
                raise OSError("Failed to verify written result file.")
            rec = GeneratedFile(
                file_id=file_id,
                filename=safe_name,
                media_type=media_type,
                size_bytes=target.stat().st_size,
                task_id=task_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                user_id=user_id,
                tool_name=tool_name,
                meta=copy.deepcopy(meta) if meta else {},
            )
            self._index[file_id] = rec
            try:
                self._save()
            except Exception:
                self._index.pop(file_id, None)
                target.unlink(missing_ok=True)
                raise
            return copy.deepcopy(rec)

    def cleanup_older_than(self, max_age_seconds: float) -> int:
        """Delete result files older than ``max_age_seconds``. Returns count removed."""
        with self._lock:
            now = datetime.now(timezone.utc)
            removed = 0
            for fid, rec in list(self._index.items()):
                try:
                    created = datetime.fromisoformat(rec.created_at)
                except ValueError:
                    continue
                if (now - created).total_seconds() < max_age_seconds:
                    continue
                path = self.absolute_path(fid)
                if path and path.exists():
                    try:
                        path.unlink()
                    except OSError:
                        continue
                del self._index[fid]
                removed += 1
            if removed:
                self._save()
            return removed
