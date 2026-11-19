"""``AttachmentManager`` - the multimodal attachment pipeline.
Pipeline: Upload -> Validation -> Parsing -> Extraction -> Chunking ->
Context/Retrieval -> Model -> Response.
Design notes (security / privacy, per Part 8 spec):
- Uploaded bytes are written under a dedicated temp directory
  (``ATTACHMENT_STORAGE_DIR``), *not* inside the Desktop Agent's filesystem
  sandbox (``AGENT_WORKSPACE_DIR``) - Desktop Agent tools cannot reach
  attachment files, and attachments cannot reach the Desktop Agent's
  workspace.
- The on-disk filename is always ``<uuid>.<validated-extension>`` - the
  client's original filename is never used as a path component.
- For documents, the temp file is deleted immediately after text is
  extracted; only the (size-bounded) extracted text/chunks stay in memory.
  For images, the temp file is kept only until TTL expiry or explicit
  deletion, since the raw bytes are needed for vision calls.
- Nothing here ever logs file content - only ids/filenames/sizes/errors.
- Nothing here ever executes, evaluates, or shells out to file content.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from app.attachments.chunking import chunk_text, select_relevant_chunks
from app.attachments.models import AttachmentKind, AttachmentRecord, AttachmentStatus
from app.attachments.validation import validate_upload
from app.config.settings import Settings, get_settings
from app.core.logging_config import get_logger
from app.core.paths import resolve_under_project_root
from app.documents.processor import DocumentProcessor, build_default_document_processor
from app.models.errors import (
    AttachmentNotFoundError,
    AttachmentProcessingTimeoutError,
    DocumentParsingError,
    DocumentTooLargeError,
    TooManyConcurrentJobsError,
)
logger = get_logger("nexa.attachments")
@dataclass
class _Stored:
    record: AttachmentRecord
    extension: str
    text: str | None = None
    chunks: list[str] = field(default_factory=list)
    temp_path: Path | None = None
class AttachmentManager:
    def __init__(
        self,
        storage_dir: Path,
        document_processor: DocumentProcessor,
        *,
        max_size_bytes: int,
        max_attachments_per_message: int,
        processing_timeout_seconds: float,
        max_concurrent_jobs: int,
        ttl_seconds: float,
        context_max_chars: int,
    ) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._storage_dir / ".ownership.json"
        self._manifest_lock = threading.RLock()
        self._processor = document_processor
        self._max_size_bytes = max_size_bytes
        self.max_attachments_per_message = max_attachments_per_message
        self._timeout = processing_timeout_seconds
        self._max_concurrent = max_concurrent_jobs
        self._ttl = ttl_seconds
        self._context_max_chars = context_max_chars
        self._records: dict[str, _Stored] = {}
        self._active_jobs = 0
        self._active_lock = asyncio.Lock()
    # --- lifecycle -----------------------------------------------------------
    def cleanup_expired(self) -> int:
        """Delete expired attachments (temp files + in-memory record). Returns count removed."""
        now = time.time()
        expired = {
            attachment_id
            for attachment_id, stored in self._records.items()
            if stored.record.expires_at is not None and stored.record.expires_at.timestamp() < now
        }
        manifest = self._read_manifest()
        for attachment_id, entry in manifest.items():
            try:
                if float(entry["expires_at"]) < now:
                    expired.add(attachment_id)
            except (KeyError, TypeError, ValueError):
                # A malformed entry is not trusted as a filesystem path.
                continue
        for attachment_id in expired:
            self._discard(attachment_id)
        if expired:
            logger.info("attachments cleanup removed=%d", len(expired))
        return len(expired)
    def _read_manifest(self) -> dict[str, dict]:
        with self._manifest_lock:
            if not self._manifest_path.exists():
                return {}
            try:
                raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError("Attachment ownership manifest is unreadable; refusing unsafe cleanup.") from exc
            if not isinstance(raw, dict):
                raise RuntimeError("Attachment ownership manifest has an invalid format.")
            return {
                key: value for key, value in raw.items()
                if isinstance(key, str) and isinstance(value, dict)
            }

    def _write_manifest(self, manifest: dict[str, dict]) -> None:
        with self._manifest_lock:
            fd, temp_name = tempfile.mkstemp(prefix=".ownership-", dir=self._storage_dir)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(manifest, stream, ensure_ascii=False, separators=(",", ":"))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_name, self._manifest_path)
                try:
                    os.chmod(self._manifest_path, 0o600)
                except OSError:
                    pass
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)

    def _record_manifest(self, record: AttachmentRecord, temp_path: Path) -> None:
        if not record.user_id:
            return
        filename = temp_path.name
        if filename != f"{record.id}.{record.format}":
            raise RuntimeError("Unexpected attachment storage filename.")
        manifest = self._read_manifest()
        manifest[record.id] = {
            "user_id": record.user_id,
            "filename": filename,
            "expires_at": record.expires_at.timestamp() if record.expires_at else 0,
        }
        self._write_manifest(manifest)

    def _forget_manifest(self, attachment_id: str) -> None:
        manifest = self._read_manifest()
        if attachment_id in manifest:
            manifest.pop(attachment_id, None)
            self._write_manifest(manifest)

    def _safe_manifest_file(self, attachment_id: str, entry: dict) -> Path | None:
        if not re.fullmatch(r"[0-9a-f]{32}", attachment_id):
            return None
        filename = entry.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            return None
        if not re.fullmatch(rf"{attachment_id}\.[a-z0-9]{{1,10}}", filename):
            return None
        candidate = self._storage_dir / filename
        if candidate.is_symlink():
            return candidate
        try:
            resolved = candidate.resolve()
            root = self._storage_dir.resolve()
        except OSError:
            return None
        if resolved.parent != root:
            return None
        return candidate

    def _discard(self, attachment_id: str) -> None:
        stored = self._records.pop(attachment_id, None)
        if stored and stored.temp_path:
            stored.temp_path.unlink(missing_ok=True)
        manifest = self._read_manifest()
        entry = manifest.pop(attachment_id, None)
        if entry:
            candidate = self._safe_manifest_file(attachment_id, entry)
            if candidate:
                candidate.unlink(missing_ok=True)
            self._write_manifest(manifest)
    # --- upload pipeline -------------------------------------------------------
    def _owned(self, stored: _Stored, user_id: str | None) -> bool:
        """True when ``user_id`` may access the record (None = no ownership filter)."""
        if user_id is None:
            return True
        return stored.record.user_id == user_id

    async def upload(
        self, filename: str, raw: bytes, *, user_id: str | None = None
    ) -> AttachmentRecord:
        """Run the full pipeline for one uploaded file and return its public record."""
        self.cleanup_expired()
        extension, kind, mime_type = validate_upload(filename, raw, max_size_bytes=self._max_size_bytes)
        attachment_id = uuid.uuid4().hex
        expires_at = _future(self._ttl)
        record = AttachmentRecord(
            id=attachment_id,
            filename=_display_name(filename),
            mime_type=mime_type,
            format=extension,
            size_bytes=len(raw),
            kind=kind,
            status=AttachmentStatus.PROCESSING,
            expires_at=expires_at,
            user_id=user_id,
        )
        stored = _Stored(record=record, extension=extension)
        self._records[attachment_id] = stored
        async with self._active_lock:
            if self._active_jobs >= self._max_concurrent:
                self._fail(stored, "Too many attachments are being processed right now. Try again shortly.")
                raise TooManyConcurrentJobsError()
            self._active_jobs += 1
        try:
            temp_path = self._storage_dir / f"{attachment_id}.{extension}"
            temp_path.write_bytes(raw)
            stored.temp_path = temp_path
            try:
                self._record_manifest(record, temp_path)
            except Exception:
                self._delete_temp(stored)
                raise
            if kind == AttachmentKind.IMAGE:
                stored.record.status = AttachmentStatus.READY
                logger.info("attachment ready id=%s kind=image format=%s size=%d", attachment_id, extension, len(raw))
            else:
                await self._process_document(stored, raw, extension)
        except (DocumentParsingError, DocumentTooLargeError) as exc:
            self._fail(stored, exc.message)
        except TimeoutError:
            self._fail(stored, AttachmentProcessingTimeoutError().message)
            self._delete_temp(stored)
        finally:
            async with self._active_lock:
                self._active_jobs -= 1
        return stored.record.model_copy()
    async def _process_document(self, stored: _Stored, raw: bytes, extension: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            parsed = await asyncio.wait_for(
                loop.run_in_executor(None, self._processor.process, raw, stored.record.filename),
                timeout=self._timeout,
            )
        finally:
            # Documents never need the raw bytes again once parsed - delete
            # the temp file immediately regardless of success or failure.
            self._delete_temp(stored)
        stored.text = parsed.text
        stored.chunks = chunk_text(parsed.text)
        stored.record.status = AttachmentStatus.READY
        stored.record.char_count = len(parsed.text)
        stored.record.chunk_count = len(stored.chunks)
        stored.record.page_count = parsed.metadata.get("page_count")
        stored.record.truncated = bool(parsed.metadata.get("truncated", False))
        stored.record.text_preview = parsed.text[:500]
        logger.info(
            "attachment ready id=%s kind=document format=%s chars=%d chunks=%d",
            stored.record.id,
            extension,
            stored.record.char_count,
            stored.record.chunk_count,
        )
    def _delete_temp(self, stored: _Stored) -> None:
        if stored.temp_path and stored.temp_path.exists():
            stored.temp_path.unlink(missing_ok=True)
        stored.temp_path = None
        self._forget_manifest(stored.record.id)
    def _fail(self, stored: _Stored, message: str) -> None:
        stored.record.status = AttachmentStatus.FAILED
        stored.record.error = message
        logger.warning("attachment failed id=%s error=%s", stored.record.id, message)
    # --- retrieval -------------------------------------------------------------
    def get(self, attachment_id: str, *, user_id: str | None = None) -> AttachmentRecord:
        self.cleanup_expired()
        stored = self._records.get(attachment_id)
        if stored is None or not self._owned(stored, user_id):
            raise AttachmentNotFoundError(attachment_id)
        return stored.record.model_copy()
    def get_text(self, attachment_id: str, *, user_id: str | None = None) -> str:
        """Return the full (already size-bounded) extracted text for one document.
        Raises:
            app.models.errors.AttachmentNotFoundError: If the id is unknown/expired.
        """
        self.cleanup_expired()
        stored = self._records.get(attachment_id)
        if stored is None or not self._owned(stored, user_id):
            raise AttachmentNotFoundError(attachment_id)
        return stored.text or ""
    def list(self, *, user_id: str | None = None) -> list[AttachmentRecord]:
        self.cleanup_expired()
        return [
            stored.record.model_copy()
            for stored in self._records.values()
            if self._owned(stored, user_id)
        ]
    def delete(self, attachment_id: str, *, user_id: str | None = None) -> None:
        self.cleanup_expired()
        stored = self._records.get(attachment_id)
        if stored is None or not self._owned(stored, user_id):
            raise AttachmentNotFoundError(attachment_id)
        self._discard(attachment_id)

    def delete_user(self, user_id: str) -> int:
        """Remove all attachments owned by ``user_id``. Returns count deleted."""
        manifest = self._read_manifest()
        persisted_ids = {
            aid for aid, entry in manifest.items() if entry.get("user_id") == user_id
        }
        memory_ids = {
            aid for aid, stored in self._records.items()
            if stored.record.user_id == user_id
        }
        for aid in persisted_ids | memory_ids:
            self._discard(aid)
        return len(persisted_ids | memory_ids)

    def resolve_ids(
        self, attachment_ids: list[str], *, user_id: str | None = None
    ) -> list[AttachmentRecord]:
        """Return ready records for ``attachment_ids``, in the given order.
        Raises:
            app.models.errors.AttachmentNotFoundError: If any id is unknown/expired
            or not owned by ``user_id`` when that filter is set.
        """
        self.cleanup_expired()
        records: list[AttachmentRecord] = []
        for attachment_id in attachment_ids:
            stored = self._records.get(attachment_id)
            if stored is None or not self._owned(stored, user_id):
                raise AttachmentNotFoundError(attachment_id)
            records.append(stored.record)
        return records
    def document_context(self, attachment_ids: list[str], query: str, max_chars: int | None = None, *, user_id: str | None = None) -> str:
        """Build a bounded "Document Context" block for ``attachment_ids``.
        Only document-kind, successfully-processed attachments contribute.
        Never returns a raw full-document dump - always chunk-selected and
        capped at ``max_chars``.
        """
        self.cleanup_expired()
        budget = max_chars or self._context_max_chars
        doc_ids = [
            attachment_id
            for attachment_id in attachment_ids
            if (stored := self._records.get(attachment_id)) is not None
            and self._owned(stored, user_id)
            and stored.record.kind == AttachmentKind.DOCUMENT
            and stored.record.status == AttachmentStatus.READY
        ]
        if not doc_ids:
            return ""
        per_doc_budget = max(budget // len(doc_ids), 500)
        parts: list[str] = []
        used = 0
        for attachment_id in doc_ids:
            stored = self._records[attachment_id]
            remaining = min(per_doc_budget, budget - used)
            if remaining <= 0:
                break
            relevant = select_relevant_chunks(stored.chunks, query, remaining)
            if not relevant:
                continue
            block = f"[{stored.record.filename}]\n" + "\n".join(relevant)
            parts.append(block)
            used += len(block)
        return "\n\n".join(parts)[:budget]
    def image_payloads(self, attachment_ids: list[str], *, user_id: str | None = None) -> list[tuple[bytes, str]]:
        """Return ``(raw_bytes, mime_type)`` for the image-kind ids in ``attachment_ids``."""
        self.cleanup_expired()
        payloads: list[tuple[bytes, str]] = []
        for attachment_id in attachment_ids:
            stored = self._records.get(attachment_id)
            if stored is None or not self._owned(stored, user_id) or stored.record.kind != AttachmentKind.IMAGE:
                continue
            if stored.record.status != AttachmentStatus.READY or stored.temp_path is None:
                continue
            payloads.append((stored.temp_path.read_bytes(), stored.record.mime_type))
        return payloads
    def has_images(self, attachment_ids: list[str], *, user_id: str | None = None) -> bool:
        self.cleanup_expired()
        return any(
            (stored := self._records.get(attachment_id)) is not None
            and self._owned(stored, user_id)
            and stored.record.kind == AttachmentKind.IMAGE
            for attachment_id in attachment_ids
        )
def _display_name(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:200] if name else "file"
def _future(seconds: float):
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)
def build_attachment_manager(settings: Settings) -> AttachmentManager:
    processor = build_default_document_processor(
        max_size_bytes=settings.max_attachment_size_bytes,
        max_pages=settings.max_document_pages,
        max_text_chars=settings.max_extracted_text_chars,
    )
    storage_dir = resolve_under_project_root(settings.attachment_storage_dir)
    return AttachmentManager(
        storage_dir=storage_dir,
        document_processor=processor,
        max_size_bytes=settings.max_attachment_size_bytes,
        max_attachments_per_message=settings.max_attachments_per_message,
        processing_timeout_seconds=settings.attachment_processing_timeout_seconds,
        max_concurrent_jobs=settings.max_concurrent_attachment_jobs,
        ttl_seconds=settings.attachment_ttl_seconds,
        context_max_chars=settings.attachment_context_max_chars,
    )
@lru_cache
def get_attachment_manager() -> AttachmentManager:
    """Process-wide cached manager. Tests needing isolation should construct
    :class:`AttachmentManager` directly or call ``get_attachment_manager.cache_clear()``.
    """
    return build_attachment_manager(get_settings())
