"""Shared execution wrapper: task id, timeout, verified result payload."""
from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.logging_config import get_logger
from app.tools.base import ToolResult
from app.tools.office.result_store import GeneratedFile, ResultStore

logger = get_logger("nexa.tools.office")

DEFAULT_TIMEOUT_SECONDS = 45.0


async def run_office_job(
    *,
    tool_name: str,
    store: ResultStore,
    build: Callable[[str], Awaitable[tuple[bytes, str, str, dict[str, Any]]]],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    user_id: str | None = None,
    task_id: str | None = None,
) -> ToolResult:
    """
    ``build(task_id)`` returns ``(bytes, filename_stem_or_name, extension, meta)``.
    Verifies file on disk before reporting success.
    """
    tid = (task_id or uuid.uuid4().hex)[:32]
    started = time.perf_counter()
    logger.info("office_job_start tool=%s task_id=%s", tool_name, tid)
    try:
        data, filename, extension, meta = await asyncio.wait_for(
            build(tid), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning("office_job_timeout tool=%s task_id=%s", tool_name, tid)
        return ToolResult(
            success=False,
            error=f"{tool_name} timed out after {timeout_seconds:.0f}s.",
            metadata={"task_id": tid, "status": "timeout"},
        )
    except ValueError as exc:
        return ToolResult(
            success=False,
            error=str(exc),
            metadata={"task_id": tid, "status": "invalid_input"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "office_job_error tool=%s task_id=%s err=%s",
            tool_name,
            tid,
            exc.__class__.__name__,
        )
        return ToolResult(
            success=False,
            error=f"{tool_name} failed: {exc.__class__.__name__}",
            metadata={"task_id": tid, "status": "error"},
        )

    media = _media_type(extension)
    try:
        rec = store.save_bytes(
            data,
            filename=filename,
            media_type=media,
            extension=extension,
            task_id=tid,
            tool_name=tool_name,
            user_id=user_id,
            meta=meta,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("office_job_save_failed tool=%s task_id=%s", tool_name, tid)
        return ToolResult(
            success=False,
            error=f"Could not save generated file: {exc.__class__.__name__}",
            metadata={"task_id": tid, "status": "save_failed"},
        )

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "office_job_done tool=%s task_id=%s file_id=%s size=%d elapsed_ms=%.1f",
        tool_name,
        tid,
        rec.file_id,
        rec.size_bytes,
        elapsed_ms,
    )
    return ToolResult(
        success=True,
        output=_public_payload(rec, meta),
        metadata={
            "task_id": tid,
            "status": "ok",
            "file_id": rec.file_id,
            "elapsed_ms": round(elapsed_ms, 2),
        },
    )


def _public_payload(rec: GeneratedFile, meta: dict[str, Any]) -> dict[str, Any]:
    """Client-safe result — download URL only, never absolute server paths."""
    return {
        "file_id": rec.file_id,
        "filename": rec.filename,
        "download_url": rec.download_path,
        "media_type": rec.media_type,
        "size_bytes": rec.size_bytes,
        "task_id": rec.task_id,
        "slides": meta.get("slides"),
        "sections": meta.get("sections"),
        "rows": meta.get("rows"),
        "summary": meta.get("summary"),
    }


def _media_type(extension: str) -> str:
    ext = extension.lstrip(".").lower()
    return {
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }.get(ext, "application/octet-stream")
