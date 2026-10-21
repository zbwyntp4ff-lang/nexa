"""Attachment endpoints (Part 8): upload, metadata, retrieval, deletion.
Implements: Upload -> Validation -> Parsing -> Extraction -> Chunking, per
the multimodal attachment pipeline in :mod:`app.attachments.manager`. Raw
file bytes and full extracted text never leave this module's manager - the
API only ever returns bounded metadata/previews.

Multi-tenant: uploads are stamped with the session user; get/delete/content
require ownership (404 for other users' ids).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.api.security_deps import require_user_when_enforced
from app.attachments.manager import AttachmentManager, get_attachment_manager
from app.attachments.models import AttachmentRecord
from app.auth.models import UserRecord
from app.config.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])


class AttachmentLimits:
    def __init__(self, settings: Settings) -> None:
        self.max_size_bytes = settings.max_attachment_size_bytes
        self.max_attachments_per_message = settings.max_attachments_per_message
        self.max_document_pages = settings.max_document_pages
        self.max_extracted_text_chars = settings.max_extracted_text_chars
        self.processing_timeout_seconds = settings.attachment_processing_timeout_seconds
        self.max_concurrent_jobs = settings.max_concurrent_attachment_jobs
        self.ttl_seconds = settings.attachment_ttl_seconds


def _manager_dep() -> AttachmentManager:
    return get_attachment_manager()


def _uid(user: UserRecord | None) -> str | None:
    return user.id if user is not None else None


@router.get("/limits")
async def get_limits(settings: Settings = Depends(get_settings)) -> dict:
    limits = AttachmentLimits(settings)
    return {
        "max_size_bytes": limits.max_size_bytes,
        "max_attachments_per_message": limits.max_attachments_per_message,
        "max_document_pages": limits.max_document_pages,
        "max_extracted_text_chars": limits.max_extracted_text_chars,
        "processing_timeout_seconds": limits.processing_timeout_seconds,
        "max_concurrent_jobs": limits.max_concurrent_jobs,
        "ttl_seconds": limits.ttl_seconds,
    }


@router.post("", response_model=AttachmentRecord)
async def upload_attachment(
    file: UploadFile,
    manager: AttachmentManager = Depends(_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> AttachmentRecord:
    raw = await file.read()
    return await manager.upload(file.filename or "file", raw, user_id=_uid(user))


@router.get("/{attachment_id}", response_model=AttachmentRecord)
async def get_attachment(
    attachment_id: str,
    manager: AttachmentManager = Depends(_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> AttachmentRecord:
    return manager.get(attachment_id, user_id=_uid(user))


@router.get("/{attachment_id}/content")
async def get_attachment_content(
    attachment_id: str,
    manager: AttachmentManager = Depends(_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> dict:
    """Return the extracted text for a document attachment (bounded, never raw bytes)."""
    record = manager.get(attachment_id, user_id=_uid(user))
    text = manager.get_text(attachment_id, user_id=_uid(user))
    return {"id": record.id, "filename": record.filename, "format": record.format, "text": text}


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    manager: AttachmentManager = Depends(_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> dict:
    manager.delete(attachment_id, user_id=_uid(user))
    return {"deleted": True, "id": attachment_id}
