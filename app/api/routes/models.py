"""Model gateway endpoints.
Lists models, updates the in-memory selection, and checks availability.
API keys are never included in any response.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, get_nexa_core, get_settings
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.auth.service import AuthService
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


def require_model_admin(
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Only the configured NEXA owner may mutate or probe global model settings.

    In local non-enforced desktop mode, unauthenticated local operation remains
    available. In enforced/multi-user mode, a valid owner session is mandatory.
    """
    if user is None:
        if settings.tokens_enforce:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return
    if not auth.is_owner(user):
        raise HTTPException(status_code=403, detail="Only the NEXA owner can change global model settings.")


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
        last_display_name=info.display_name,
        models=cards,
    )


@router.put("/models/selection", response_model=ModelsResponse, dependencies=[Depends(require_model_admin)])
async def update_selection(
    body: SelectionUpdate, core: NexaCore = Depends(get_nexa_core)
) -> ModelsResponse:
    gateway = _gateway(core)
    gateway.set_selection(body.provider, body.model, body.allow_fallback)
    return await list_models(core)


@router.post("/models/check", response_model=ModelCard, dependencies=[Depends(require_model_admin)])
async def check_model(
    body: CheckRequest, core: NexaCore = Depends(get_nexa_core)
) -> ModelCard:
    gateway = _gateway(core)
    target = body.model
    if target.strip().lower() == "auto":
        target = core.model_info().model
    return await gateway.check(target, live=body.live)
