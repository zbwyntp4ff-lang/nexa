"""Multi-provider multimodal attachments (Part 8).
Pipeline: Upload -> Validation -> Parsing -> Extraction -> Chunking ->
Context/Retrieval -> Model -> Response. See ``app.attachments.manager``.
"""
from app.attachments.manager import AttachmentManager, get_attachment_manager
from app.attachments.models import AttachmentKind, AttachmentRecord, AttachmentStatus
__all__ = [
    "AttachmentManager",
    "get_attachment_manager",
    "AttachmentKind",
    "AttachmentRecord",
    "AttachmentStatus",
]
