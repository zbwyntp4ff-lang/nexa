"""A tool that returns the current UTC time."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from app.tools.base import Tool, ToolResult
class CurrentTimeTool(Tool):
    name = "current_time"
    description = "Return the current date and time (UTC, ISO 8601)."
    input_schema = {"type": "object", "properties": {}}
    permissions = frozenset({"time"})
    async def execute(self, **kwargs: Any) -> ToolResult:
        now = datetime.now(timezone.utc)
        return ToolResult(success=True, output=now.isoformat())
