"""Profile business logic — own-user only."""
from __future__ import annotations

from app.profile.context import build_compact_hint, resolve_preferred_model
from app.profile.models import (
    AIPreferences,
    ProfileUpdate,
    ProjectPersonalization,
    UserProfile,
    utcnow,
)
from app.profile.store import ProfileStore

_MAX_AVATAR_CHARS = 120_000  # ~small data-URL; reject huge payloads
_MAX_DISPLAY_NAME = 64


class ProfileService:
    def __init__(self, store: ProfileStore) -> None:
        self._store = store

    def get_or_create(self, user_id: str, *, display_name_hint: str = "") -> UserProfile:
        existing = self._store.get(user_id)
        if existing:
            return existing
        profile = UserProfile(
            user_id=user_id,
            display_name=(display_name_hint or "")[:_MAX_DISPLAY_NAME],
        )
        return self._store.save(profile)

    def get(self, user_id: str) -> UserProfile | None:
        return self._store.get(user_id)

    def update(self, user_id: str, patch: ProfileUpdate) -> UserProfile:
        profile = self.get_or_create(user_id)
        data = profile.model_dump()
        if patch.display_name is not None:
            data["display_name"] = patch.display_name.strip()[:_MAX_DISPLAY_NAME]
        if patch.avatar_data_url is not None:
            avatar = patch.avatar_data_url.strip()
            if avatar and not avatar.startswith("data:image/"):
                avatar = ""
            if len(avatar) > _MAX_AVATAR_CHARS:
                avatar = ""
            data["avatar_data_url"] = avatar or None
        if patch.ui_language is not None:
            data["ui_language"] = patch.ui_language.strip()[:16]
        if patch.theme is not None:
            theme = patch.theme.strip().lower()
            data["theme"] = theme if theme in {"", "light", "dark", "system"} else ""
        if patch.ai is not None:
            data["ai"] = patch.ai.model_dump()
        if patch.onboarding_completed is not None:
            data["onboarding_completed"] = bool(patch.onboarding_completed)
        data["updated_at"] = utcnow()
        updated = UserProfile.model_validate(data)
        return self._store.save(updated)

    def public_dict(self, profile: UserProfile) -> dict:
        """Safe public shape — never includes secrets (profiles never store them)."""
        return profile.model_dump(mode="json")

    def compact_hint(
        self,
        user_id: str,
        project: ProjectPersonalization | None = None,
    ) -> str | None:
        profile = self.get(user_id)
        if not profile:
            return None
        return build_compact_hint(profile, project)

    def preferred_model(
        self,
        user_id: str,
        project: ProjectPersonalization | None = None,
    ) -> str | None:
        profile = self.get(user_id)
        if not profile:
            return project.preferred_model if project else None
        return resolve_preferred_model(profile, project)

    def default_ai(self) -> AIPreferences:
        return AIPreferences()
