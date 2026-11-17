"""Write a text file inside the agent's sandboxed workspace directory."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app.models.errors import PathTraversalError
from app.tools.base import Tool, ToolResult
from app.tools.sandbox import resolve_safe_path, user_workspace_root
class FileWriteTool(Tool):
    name = "file_write"
    description = "Write text content to a file inside the agent workspace sandbox."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace sandbox."},
            "content": {"type": "string", "description": "Text content to write."},
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite an existing file (default true).",
            },
        },
        "required": ["path", "content"],
    }
    permissions = frozenset({"filesystem:write"})
    def __init__(self, sandbox_root: Path) -> None:
        self._sandbox_root = sandbox_root
    async def execute(self, **kwargs: Any) -> ToolResult:
        raw_path = kwargs.get("path")
        content = kwargs.get("content")
        overwrite = kwargs.get("overwrite", True)
        if not raw_path or not isinstance(raw_path, str):
            return ToolResult(success=False, error="'path' must be a non-empty string.")
        if content is None or not isinstance(content, str):
            return ToolResult(success=False, error="'content' must be a string.")
        try:
            target = resolve_safe_path(user_workspace_root(self._sandbox_root, kwargs.get("user_id")), raw_path)
        except PathTraversalError as exc:
            return ToolResult(success=False, error=str(exc))
        if target.exists() and not overwrite:
            return ToolResult(success=False, error=f"File already exists: {raw_path}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, error=f"Could not write file: {exc}")
        return ToolResult(
            success=True,
            output=f"Wrote {len(content)} characters to {raw_path}",
            metadata={"path": raw_path, "bytes": len(content.encode("utf-8"))},
        )
