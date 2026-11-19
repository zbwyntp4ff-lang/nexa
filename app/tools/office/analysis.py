"""FileAnalysisTool — inspect existing documents inside the agent sandbox."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from app.core.logging_config import get_logger
from app.documents.processor import build_default_document_processor
from app.models.errors import (
    DocumentParsingError,
    DocumentTooLargeError,
    PathTraversalError,
    UnsupportedDocumentFormatError,
)
from app.tools.base import Tool, ToolResult
from app.tools.sandbox import resolve_safe_path, user_workspace_root

logger = get_logger("nexa.tools.office.analysis")

_MAX_SUMMARY_CHARS = 4000


class FileAnalysisTool(Tool):
    name = "analyze_file"
    description = (
        "Analyze an existing document in the agent workspace (PDF, DOCX, XLSX, TXT, CSV, JSON). "
        "Returns extracted text summary, page/structure metadata — not a rewrite of the file."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the agent workspace sandbox.",
            },
            "max_chars": {"type": "integer", "description": "Max characters of extracted text."},
        },
        "required": ["path"],
    }
    permissions = frozenset({"filesystem:read"})

    def __init__(self, sandbox_root: Path) -> None:
        self._sandbox_root = sandbox_root
        self._processor = build_default_document_processor(
            max_size_bytes=20_000_000,
            max_text_chars=_MAX_SUMMARY_CHARS,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        task_id = uuid.uuid4().hex[:16]
        started = time.perf_counter()
        raw_path = kwargs.get("path")
        if not raw_path or not isinstance(raw_path, str):
            return ToolResult(
                success=False,
                error="'path' must be a non-empty string.",
                metadata={"task_id": task_id, "status": "invalid_input"},
            )
        max_chars = kwargs.get("max_chars")
        limit = _MAX_SUMMARY_CHARS
        if isinstance(max_chars, int) and 200 <= max_chars <= 50_000:
            limit = max_chars

        try:
            target = resolve_safe_path(user_workspace_root(self._sandbox_root, kwargs.get("user_id")), raw_path)
        except PathTraversalError as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                metadata={"task_id": task_id, "status": "path_error"},
            )
        if not target.is_file():
            return ToolResult(
                success=False,
                error=f"File not found in workspace: {raw_path}",
                metadata={"task_id": task_id, "status": "not_found"},
            )

        try:
            data = target.read_bytes()
            parsed = self._processor.process(data, target.name)
        except UnsupportedDocumentFormatError as exc:
            return ToolResult(success=False, error=str(exc), metadata={"task_id": task_id, "status": "unsupported"})
        except DocumentTooLargeError as exc:
            return ToolResult(success=False, error=str(exc), metadata={"task_id": task_id, "status": "too_large"})
        except DocumentParsingError as exc:
            return ToolResult(success=False, error=str(exc), metadata={"task_id": task_id, "status": "parse_error"})
        except Exception as exc:  # noqa: BLE001
            logger.error("analyze_file failed task_id=%s err=%s", task_id, exc.__class__.__name__)
            return ToolResult(
                success=False,
                error=f"Analysis failed: {exc.__class__.__name__}",
                metadata={"task_id": task_id, "status": "error"},
            )

        text = (parsed.text or "")[:limit]
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "analyze_file_done task_id=%s path=%s chars=%d elapsed_ms=%.1f",
            task_id,
            raw_path,
            len(text),
            elapsed_ms,
        )
        return ToolResult(
            success=True,
            output={
                "path": raw_path,
                "filename": target.name,
                "format": target.suffix.lstrip(".").lower(),
                "size_bytes": target.stat().st_size,
                "char_count": len(text),
                "text_preview": text,
                "metadata": parsed.metadata,
                "summary": f"Analyzed {target.name}: {len(text)} characters extracted.",
            },
            metadata={"task_id": task_id, "status": "ok", "elapsed_ms": round(elapsed_ms, 2)},
        )
