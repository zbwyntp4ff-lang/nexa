"""Rename a file or directory inside the agent workspace sandbox."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app.models.errors import PathTraversalError
from app.tools.base import Tool, ToolResult
from app.tools.sandbox import resolve_safe_path
class FileRenameTool(Tool):
    name = "file_rename"
    description = "Rename a file or directory inside the agent workspace sandbox."
    input_schema = {
        "type": "object",
        "properties": {
            "old_path": {"type": "string", "description": "Current path relative to the workspace sandbox."},
            "new_path": {"type": "string", "description": "New path relative to the workspace sandbox."},
        },
        "required": ["old_path", "new_path"],
    }
    permissions = frozenset({"filesystem:write"})
    def __init__(self, sandbox_root: Path) -> None:
        self._sandbox_root = sandbox_root
    async def execute(self, **kwargs: Any) -> ToolResult:
        old_path = kwargs.get("old_path")
        new_path = kwargs.get("new_path")
        if not old_path or not isinstance(old_path, str):
            return ToolResult(success=False, error="'old_path' must be a non-empty string.")
        if not new_path or not isinstance(new_path, str):
            return ToolResult(success=False, error="'new_path' must be a non-empty string.")
        try:
            old_target = resolve_safe_path(self._sandbox_root, old_path)
            new_target = resolve_safe_path(self._sandbox_root, new_path)
        except PathTraversalError as exc:
            return ToolResult(success=False, error=str(exc))
        if not old_target.exists():
            return ToolResult(success=False, error=f"Source not found: {old_path}")
        if new_target.exists():
            return ToolResult(success=False, error=f"Destination already exists: {new_path}")
        try:
            new_target.parent.mkdir(parents=True, exist_ok=True)
            old_target.rename(new_target)
        except OSError as exc:
            return ToolResult(success=False, error=f"Could not rename: {exc}")
        return ToolResult(
            success=True,
            output=f"Renamed {old_path} → {new_path}",
            metadata={"old_path": old_path, "new_path": new_path},
        )
