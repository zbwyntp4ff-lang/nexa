"""Register connected plugin adapters as Tool Registry entries (no duplicate builtins)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.secrets import redact_secrets
from app.tools.base import Tool, ToolResult

if TYPE_CHECKING:
    from app.plugins.manager import PluginManager


class PluginDispatchTool(Tool):
    """One tool per connected plugin: ``plugin_<id>``."""

    def __init__(self, manager: PluginManager, plugin_id: str) -> None:
        adapter = manager.adapter(plugin_id)
        self.name = f"plugin_{plugin_id}"
        self.description = adapter.manifest.description
        self.permissions = frozenset(adapter.manifest.required_permissions)
        self.input_schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "params": {"type": "object"},
                "confirm": {"type": "boolean"},
            },
            "required": ["action"],
        }
        self._manager = manager
        self._plugin_id = plugin_id

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action") or "")
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        confirm = bool(kwargs.get("confirm"))
        try:
            result = await self._manager.invoke(
                self._plugin_id, action, params, confirm=confirm
            )
        except Exception as exc:  # noqa: BLE001 - tool contract: return failure
            return ToolResult(success=False, error=redact_secrets(str(exc)))
        return ToolResult(
            success=result.success,
            output=result.output,
            error=redact_secrets(result.error) if result.error else None,
            metadata=result.metadata,
        )
