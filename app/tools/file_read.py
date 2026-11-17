"""Read a text file from within the agent's sandboxed workspace directory."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app.models.errors import PathTraversalError
from app.tools.base import Tool, ToolResult
from app.tools.sandbox import resolve_safe_path, user_workspace_root
class FileReadTool(Tool):
    name = "file_read"
    description = "Read the contents of a text file inside the agent workspace sandbox."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace sandbox."}
        },
        "required": ["path"],
    }
    permissions = frozenset({"filesystem:read"})
    def __init__(self, sandbox_root: Path, max_bytes: int = 1_000_000) -> None:
        self._sandbox_root = sandbox_root
        self._max_bytes = max_bytes
    async def execute(self, **kwargs: Any) -> ToolResult:
        raw_path = kwargs.get("path")
        if not raw_path or not isinstance(raw_path, str):
            return ToolResult(success=False, error="'path' must be a non-empty string.")
        try:
            target = resolve_safe_path(user_workspace_root(self._sandbox_root, kwargs.get("user_id")), raw_path)
        except PathTraversalError as exc:
            return ToolResult(success=False, error=str(exc))
        if not target.exists():
            return ToolResult(success=False, error=f"File not found: {raw_path}")
        if not target.is_file():
            return ToolResult(success=False, error=f"Not a file: {raw_path}")
        if target.stat().st_size > self._max_bytes:
            return ToolResult(success=False, error=f"File too large to read: {raw_path}")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"File is not valid UTF-8 text: {raw_path}")
        except OSError as exc:
            return ToolResult(success=False, error=f"Could not read file: {exc}")
        return ToolResult(success=True, output=content, metadata={"path": raw_path})
