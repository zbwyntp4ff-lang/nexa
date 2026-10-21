"""Liveness endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from app.config.settings import get_settings
from app.models.status import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    mode = (settings.nexa_storage_mode or "persistent").strip().lower()
    if mode not in ("persistent", "ephemeral"):
        mode = "persistent"
    db_ok: bool | None = None
    try:
        from app.db.engine import get_database

        db_ok = get_database().ping()
    except Exception:  # noqa: BLE001
        db_ok = False
    provider = (settings.ai_provider or "mock").strip().lower()
    return HealthResponse(
        status="ok" if db_ok is not False else "degraded",
        version="2.0.0-cloud",
        storage_mode=mode,
        environment=settings.environment,
        database_ok=db_ok,
        ai_provider=provider,
        ollama_required=provider in ("ollama", "local"),
    )
