"""User profile / personalization API — authenticated, own-user only."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_profile_service
from app.api.routes.auth import get_current_user
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.api.deps import get_auth_service
from app.profile.models import ProfileUpdate
from app.profile.service import ProfileService

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("")
async def get_profile(
    user: Annotated[UserRecord, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    hint = f"{user.first_name} {user.last_name}".strip() or user.username
    profile = profiles.get_or_create(user.id, display_name_hint=hint)
    return {"profile": profiles.public_dict(profile)}


@router.patch("")
async def update_profile(
    body: ProfileUpdate,
    user: Annotated[UserRecord, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    # Ensure row exists for this user only — never accept client user_id.
    profiles.get_or_create(user.id)
    updated = profiles.update(user.id, body)
    return {"profile": profiles.public_dict(updated)}


@router.get("/context-preview")
async def context_preview(
    user: Annotated[UserRecord, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    """Show the compact hint that would be sent (no secrets / no memory dump)."""
    profiles.get_or_create(user.id)
    hint = profiles.compact_hint(user.id)
    return {
        "enabled": bool(hint),
        "hint": hint,
        "max_chars": 420,
    }
