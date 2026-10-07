"""Data models for the NEXA attachments subsystem.
``AttachmentRecord`` is the only thing ever returned over the API - it never
carries raw file bytes or full extracted text, only bounded metadata and a
short preview. Full text stays server-side and is retrieved in bounded
chunks by :class:`app.attachments.manager.AttachmentManager`.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
def _new_id() -> str:
    return uuid.uuid4().hex
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
class AttachmentKind(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"
class AttachmentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
class AttachmentRecord(BaseModel):
    """Public metadata for one uploaded attachment. Never includes raw content."""
    id: str = Field(default_factory=_new_id)
    filename: str
    mime_type: str
    format: str
    size_bytes: int
    kind: AttachmentKind
    status: AttachmentStatus = AttachmentStatus.PROCESSING
    error: str | None = None
    char_count: int | None = None
    chunk_count: int | None = None
    page_count: int | None = None
    truncated: bool = False
    text_preview: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
