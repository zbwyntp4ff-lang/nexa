"""Upload validation: whitelist, size, and file-signature checks.
Never trusts the client-declared filename or ``Content-Type`` alone. Binary
formats are verified against their real magic bytes so a renamed executable
cannot slip through as an "image" or "document". NEXA only ever *reads*
attachment content - nothing here parses, evaluates, or executes it.
"""
from __future__ import annotations
import zipfile
from io import BytesIO
from app.attachments.models import AttachmentKind
from app.models.errors import AttachmentTooLargeError, AttachmentValidationError, UnsupportedAttachmentFormatError
IMAGE_EXTENSIONS: frozenset[str] = frozenset({"png", "jpg", "jpeg", "webp", "gif"})
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({"txt", "md", "csv", "json", "pdf", "docx", "xlsx"})
ALLOWED_EXTENSIONS: frozenset[str] = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS
_EXTENSION_TO_MIME: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_TEXT_EXTENSIONS: frozenset[str] = frozenset({"txt", "md", "csv", "json"})
def safe_extension(filename: str) -> str:
    """Extract a lowercase extension, never trusting path separators in ``filename``."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    ext = name.rsplit(".", 1)[-1].lower().strip()
    return ext if ext.isalnum() else ""
def _looks_like_png(raw: bytes) -> bool:
    return raw.startswith(b"\x89PNG\r\n\x1a\n")
def _looks_like_jpeg(raw: bytes) -> bool:
    return raw.startswith(b"\xff\xd8\xff")
def _looks_like_gif(raw: bytes) -> bool:
    return raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a")
def _looks_like_webp(raw: bytes) -> bool:
    return len(raw) >= 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WEBP"
def _looks_like_pdf(raw: bytes) -> bool:
    return raw[:1024].lstrip(b"\x00\xef\xbb\xbf").startswith(b"%PDF-")
def _zip_member_prefix(raw: bytes) -> str | None:
    """Peek at an OOXML zip's member names (never decompresses entry contents)."""
    if not raw.startswith(b"PK\x03\x04") and not raw.startswith(b"PK\x05\x06"):
        return None
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return None
    if any(name.startswith("word/") for name in names):
        return "docx"
    if any(name.startswith("xl/") for name in names):
        return "xlsx"
    return None
_SIGNATURE_CHECKS = {
    "png": _looks_like_png,
    "jpg": _looks_like_jpeg,
    "jpeg": _looks_like_jpeg,
    "webp": _looks_like_webp,
    "gif": _looks_like_gif,
    "pdf": _looks_like_pdf,
}
def verify_signature(extension: str, raw: bytes) -> bool:
    """Return ``True`` if ``raw`` really looks like ``extension``.
    Plain-text formats (txt/md/csv/json) have no reliable magic bytes and are
    only ever decoded as text (never executed), so they are accepted here and
    rejected later by the real parser if they are not valid UTF-8/CSV/JSON.
    """
    if extension in _TEXT_EXTENSIONS:
        return b"\x00" not in raw[:4096]
    if extension in ("docx", "xlsx"):
        return _zip_member_prefix(raw) == extension
    check = _SIGNATURE_CHECKS.get(extension)
    return check(raw) if check else False
def kind_for_extension(extension: str) -> AttachmentKind:
    return AttachmentKind.IMAGE if extension in IMAGE_EXTENSIONS else AttachmentKind.DOCUMENT
def mime_for_extension(extension: str) -> str:
    return _EXTENSION_TO_MIME.get(extension, "application/octet-stream")
def validate_upload(
    filename: str,
    raw: bytes,
    *,
    max_size_bytes: int,
) -> tuple[str, AttachmentKind, str]:
    """Validate an upload and return ``(extension, kind, mime_type)``.
    Raises:
        app.models.errors.UnsupportedAttachmentFormatError
        app.models.errors.AttachmentTooLargeError
        app.models.errors.AttachmentValidationError
    """
    if not raw:
        raise AttachmentValidationError("The uploaded file is empty.")
    if len(raw) > max_size_bytes:
        raise AttachmentTooLargeError(
            f"'{filename}' is {len(raw)} bytes, exceeding the maximum of {max_size_bytes} bytes."
        )
    extension = safe_extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedAttachmentFormatError(extension or "(none)", available=tuple(sorted(ALLOWED_EXTENSIONS)))
    if not verify_signature(extension, raw):
        raise AttachmentValidationError(
            f"'{filename}' does not look like a valid .{extension} file (signature mismatch)."
        )
    return extension, kind_for_extension(extension), mime_for_extension(extension)
