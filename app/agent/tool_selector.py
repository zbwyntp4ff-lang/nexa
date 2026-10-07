"""The Tool Selector - resolves a planned tool name to a concrete, permitted ``Tool``."""
from __future__ import annotations
from app.models.errors import ToolPermissionError
from app.tools.base import Tool
from app.tools.registry import ToolRegistry
class ToolSelector:
    """Resolves tool names to instances and enforces permission constraints.
    Keeping this separate from :class:`app.agent.planner.Planner` mirrors the
    architecture diagram (Planner decides *what capability* is needed; Tool
    Selector decides *which concrete tool* satisfies it, and whether that
    tool call is currently allowed).
    """
    def __init__(self, registry: ToolRegistry, allowed_permissions: frozenset[str] | None = None) -> None:
        self._registry = registry
        self._allowed_permissions = allowed_permissions
    def select(self, tool_name: str) -> Tool:
        """Return the tool named ``tool_name``.
        Raises:
            app.models.errors.ToolNotFoundError: If no such tool is registered.
            app.models.errors.ToolPermissionError: If the tool requires
                permissions outside of ``allowed_permissions``.
        """
        tool = self._registry.get(tool_name)
        if self._allowed_permissions is not None:
            missing = tool.permissions - self._allowed_permissions
            if missing:
                raise ToolPermissionError(tool_name, missing=tuple(sorted(missing)))
        return tool
