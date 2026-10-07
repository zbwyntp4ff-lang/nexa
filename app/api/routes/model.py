"""Endpoint reporting which provider/model is currently active."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.api.deps import get_nexa_core
from app.core.nexa_core import NexaCore
from app.models.status import ModelInfoResponse
router = APIRouter(prefix="/api/v1", tags=["model"])
@router.get("/model", response_model=ModelInfoResponse)
async def model_info(core: NexaCore = Depends(get_nexa_core)) -> ModelInfoResponse:
    if core.gateway is not None:
        await core.gateway.refresh_ollama()
    return core.model_info()
