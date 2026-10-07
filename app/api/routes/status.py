"""Application status endpoint (includes a live provider health check)."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.api.deps import get_nexa_core
from app.config.settings import get_settings
from app.core.nexa_core import NexaCore
from app.models.status import StatusResponse
router = APIRouter(prefix="/api/v1", tags=["status"])
@router.get("/status", response_model=StatusResponse)
async def status(core: NexaCore = Depends(get_nexa_core)) -> StatusResponse:
    settings = get_settings()
    provider_healthy = await core.health_check()
    provider_name, _model_name = core.active_identity()
    return StatusResponse(
        status="ok" if provider_healthy else "degraded",
        app_name=settings.app_name,
        environment=settings.environment,
        provider=provider_name,
        provider_healthy=provider_healthy,
    )
