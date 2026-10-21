"""Plugin Hub models (Part 14)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PluginStatus = Literal[
    "disconnected",
    "connecting",
    "connected",
    "connected_limited",
    "missing_dependency",
    "needs_token",
    "error",
]
IntegrationType = Literal["api", "local", "browser"]
PluginCategory = Literal["editor", "git", "browser", "3d", "game"]


class PluginActionSpec(BaseModel):
    name: str
    description: str
    permissions: list[str] = Field(default_factory=list)
    dangerous: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


class PluginManifest(BaseModel):
    id: str
    version: str
    name: str
    description: str
    category: PluginCategory
    integration_type: IntegrationType
    dependencies: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    optional_permissions: list[str] = Field(default_factory=list)
    timeout_seconds: float = 20.0
    actions: list[PluginActionSpec] = Field(default_factory=list)
    install_hint: str = ""


class ProbeResult(BaseModel):
    ok: bool
    status: PluginStatus
    detail: str = ""
    version: str | None = None
    limitation: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class PluginResult(BaseModel):
    success: bool
    output: Any = None
    error: str | None = None
    needs_confirm: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PluginState(BaseModel):
    plugin_id: str
    user_id: str | None = None
    """Owner of this connection — required for multi-tenant isolation."""
    enabled: bool = False
    status: PluginStatus = "disconnected"
    granted_permissions: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # encrypted values
    last_error: str | None = None
    last_probe: str | None = None
    connected_at: str | None = None


class PluginAuditEntry(BaseModel):
    timestamp: str
    plugin_id: str
    user_id: str | None = None
    action: str
    status: str
    detail: str = ""
