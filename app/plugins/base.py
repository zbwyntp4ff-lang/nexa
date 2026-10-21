"""Plugin adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.plugins.models import PluginManifest, PluginResult, ProbeResult


@dataclass
class PluginContext:
    workspace_root: Any  # pathlib.Path
    granted_permissions: frozenset[str]
    settings: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)  # decrypted in-memory
    timeout_seconds: float = 20.0
    confirm: bool = False
    max_file_bytes: int = 1_000_000


class PluginAdapter(ABC):
    manifest: PluginManifest

    @abstractmethod
    async def probe(self, ctx: PluginContext) -> ProbeResult:
        """Check real availability. Must not report success without verification."""

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any], ctx: PluginContext) -> PluginResult:
        """Run a named action. Dangerous actions require ctx.confirm."""
