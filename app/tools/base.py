"""The ``Tool`` interface that every NEXA tool must implement."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
@dataclass
class ToolResult:
    """The outcome of a single tool execution."""
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)
class Tool(ABC):
    """Abstract base class for all NEXA tools.
    Concrete tools declare a stable ``name``, a human-readable
    ``description``, a JSON-schema-shaped ``input_schema`` describing the
    keyword arguments accepted by :meth:`execute`, and the set of
    ``permissions`` they require (checked by
    :class:`app.agent.tool_selector.ToolSelector` /
    :class:`app.tools.registry.ToolRegistry`).
    """
    name: str
    description: str
    input_schema: dict
    permissions: frozenset[str] = frozenset()
    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given keyword arguments.
        Implementations should catch their own expected failure modes and
        return a ``ToolResult(success=False, error=...)`` rather than
        raising, so :class:`app.tools.registry.ToolRegistry` can distinguish
        "the tool ran and failed" from "the tool call was invalid/not
        permitted".
        """
