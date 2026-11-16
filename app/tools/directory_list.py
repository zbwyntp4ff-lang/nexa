"""List the contents of a directory inside the agent's sandboxed workspace."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app.models.errors import PathTraversalError
from app.tools.base import Tool, ToolResult
from app.tools.sandbox import resolve_safe_path, user_workspace_root
class DirectoryListTool(Tool):
    name = "directory_list"
    description = "List files and directories inside the agent workspace sandbox."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to the workspace sandbox (default: root).",
            }
        },
    }
    permissions = frozenset({"filesystem:read"})
    def __init__(self, sandbox_root: Path) -> None:
        self._sandbox_root = sandbox_root
    async def execute(self, **kwargs: Any) -> ToolResult:
        raw_path = kwargs.get("path") or "."
        try:
            target = resolve_safe_path(user_workspace_root(self._sandbox_root, kwargs.get("user_id")), raw_path)
        except PathTraversalError as exc:
            return ToolResult(success=False, error=str(exc))
        if not target.exists():
            return ToolResult(success=False, error=f"Directory not found: {raw_path}")
        if not target.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {raw_path}")
        entries = sorted(
            (
                {"name": entry.name, "type": "directory" if entry.is_dir() else "file"}
                for entry in target.iterdir()
            ),
            key=lambda e: e["name"],
        )
        return ToolResult(success=True, output=entries, metadata={"path": raw_path})
