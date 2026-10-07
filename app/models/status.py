"""Pydantic models used for status/health/model informational endpoints."""
from __future__ import annotations
from pydantic import BaseModel
class HealthResponse(BaseModel):
    status: str = "ok"
class StatusResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    provider: str
    provider_healthy: bool
class ModelInfoResponse(BaseModel):
    provider: str
    model: str
    display_name: str | None = None
    selection_mode: str = "manual"
    allow_fallback: bool = False
    availability: str | None = None
    availability_reason: str | None = None
    last_provider: str | None = None
    last_model: str | None = None
    last_display_name: str | None = None
class ErrorResponse(BaseModel):
    """Uniform error envelope returned to API clients.
    Never contains stack traces or internal details - only a stable error
    ``code`` and a human readable ``message``.
    """
    error: str
    message: str
