"""Model gateway endpoints.
Lists models, updates the in-memory selection, and checks availability.
API keys are never included in any response.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import get_nexa_core, get_settings
from app.config.settings import Settings
from app.core.nexa_core import NexaCore
from app.gateway.models import ModelCard
from app.models.errors import ProviderConfigurationError
router = APIRouter(prefix="/api/v1", tags=["models"])
class SelectionUpdate(BaseModel):
    provider: str = Field(..., description="openai, anthropic, ollama, or auto")
    model: str = Field(..., description="A model id, or auto")
    allow_fallback: bool = False
class CheckRequest(BaseModel):
    model: str
    live: bool = True
class ModelsResponse(BaseModel):
    selection_mode: str
    provider: str | None
    model: str | None
    allow_fallback: bool
    active_provider: str
    active_model: str
    active_display_name: str | None
    availability: str | None
    availability_reason: str | None
    last_provider: str | None = None
    last_model: str | None = None
    last_display_name: str | None = None
    models: list[ModelCard]
def _gateway(core: NexaCore):
    if core.gateway is None:
        raise ProviderConfigurationError("Model gateway is not available.")
    return core.gateway
@router.get("/models", response_model=ModelsResponse)
async def list_models(core: NexaCore = Depends(get_nexa_core)) -> ModelsResponse:
    gateway = _gateway(core)
    cards = await gateway.list_models(include_mock=False)
    info = core.model_info()
    selection = gateway.selection
    return ModelsResponse(
        selection_mode=selection.mode,
        provider=selection.provider,
        model=selection.model_id,
        allow_fallback=selection.allow_fallback,
        active_provider=info.provider,
        active_model=info.model,
        active_display_name=info.display_name,
        availability=info.availability,
        availability_reason=info.availability_reason,
        last_provider=info.last_provider,
        last_model=info.last_model,
        last_display_name=info.last_display_name,
        models=cards,
    )
@router.put("/models/selection", response_model=ModelsResponse)
async def update_selection(
    body: SelectionUpdate,
    core: NexaCore = Depends(get_nexa_core),
    settings: Settings = Depends(get_settings),
) -> ModelsResponse:
    if settings.nexa_public_beta:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "beta_feature_disabled",
                "message": "Выбор модели временно отключён в публичной бета-версии.",
            },
        )
    gateway = _gateway(core)
    gateway.set_selection(body.provider, body.model, body.allow_fallback)
    return await list_models(core)
@router.post("/models/check", response_model=ModelCard)
async def check_model(
    body: CheckRequest,
    core: NexaCore = Depends(get_nexa_core),
    settings: Settings = Depends(get_settings),
) -> ModelCard:
    if settings.nexa_public_beta:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "beta_feature_disabled",
                "message": "Проверка моделей временно отключена в публичной бета-версии.",
            },
        )
    gateway = _gateway(core)
    target = body.model
    if target.strip().lower() == "auto":
        target = core.model_info().model
    return await gateway.check(target, live=body.live)
