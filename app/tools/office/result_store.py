"""Secure store for agent-generated binary results (never expose server paths)."""
from __future__ import annotations

import json
import re
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
        payload = {fid: asdict(rec) for fid, rec in self._index.items()}
        tmp = self._manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._manifest_path)

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
        """Return a result only to its exact owner.

        ``None`` is the local/unauthenticated owner. Ownerless legacy files remain
        available in local mode, but are never exposed to an authenticated user.
        This check is independent of TOKENS_ENFORCE: optional authentication must
        not turn the shared local namespace into a cross-account file namespace.
        """
        rec = self._index.get(file_id)
        if rec is None or rec.user_id != user_id:
            return None
        if self.absolute_path(file_id) is None:
            return None
        return rec
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
        file_id = uuid.uuid4().hex
        safe_name = self.sanitize_filename(filename, default="document", extension=extension)
        target = self._dir / f"{file_id}{Path(safe_name).suffix}"
        # Never overwrite an existing result id (uuid collision is astronomical).
        if target.exists():
            raise FileExistsError(f"Result path already exists: {file_id}")
        target.write_bytes(data)
        if not target.is_file() or target.stat().st_size <= 0:
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
            meta=meta or {},
        )
        self._index[file_id] = rec
        self._save()
        return rec

    def cleanup_older_than(self, max_age_seconds: float) -> int:
        """Delete result files older than ``max_age_seconds``. Returns count removed."""
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
                    pass
            del self._index[fid]
            removed += 1
        if removed:
            self._save()
        return removed
