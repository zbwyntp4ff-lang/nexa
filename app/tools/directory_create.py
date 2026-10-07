"""Create a directory inside the agent workspace sandbox."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app.models.errors import PathTraversalError
from app.tools.base import Tool, ToolResult
from app.tools.sandbox import resolve_safe_path
class DirectoryCreateTool(Tool):
    name = "directory_create"
    description = "Create a directory inside the agent workspace sandbox."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path relative to the workspace sandbox."},
        },
        "required": ["path"],
    }
    permissions = frozenset({"filesystem:write"})
    def __init__(self, sandbox_root: Path) -> None:
        self._sandbox_root = sandbox_root
    async def execute(self, **kwargs: Any) -> ToolResult:
        raw_path = kwargs.get("path")
        if not raw_path or not isinstance(raw_path, str):
            return ToolResult(success=False, error="'path' must be a non-empty string.")
        try:
            target = resolve_safe_path(self._sandbox_root, raw_path)
        except PathTraversalError as exc:
            return ToolResult(success=False, error=str(exc))
        if target.exists():
            return ToolResult(success=False, error=f"Directory already exists: {raw_path}")
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolResult(success=False, error=f"Could not create directory: {exc}")
        return ToolResult(success=True, output=f"Created directory {raw_path}", metadata={"path": raw_path})
