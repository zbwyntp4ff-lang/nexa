"""HTTP models for Plugin Hub (Part 14)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PluginConnectRequest(BaseModel):
    permissions: list[str] | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    token: str | None = Field(default=None, max_length=4000)


class PluginInvokeRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class PluginPermissionsRequest(BaseModel):
    permissions: list[str] = Field(default_factory=list)
