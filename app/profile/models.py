"""User profile + personalization (Part 11) — no secrets, minimal PII."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field

ResponseStyle = Literal["concise", "balanced", "detailed", "technical"]
Personality = Literal["professional", "friendly", "direct", "technical"]
DetailLevel = Literal["low", "medium", "high"]
AnswerFormat = Literal["auto", "prose", "bullets", "structured"]
Interest = Annotated[str, Field(max_length=60)]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIPreferences(BaseModel):
    personalization_enabled: bool = True
    response_style: ResponseStyle = "balanced"
    personality: Personality = "friendly"
    brevity: DetailLevel = "medium"
    detail_level: DetailLevel = "medium"
    answer_format: AnswerFormat = "auto"
    ai_language: str = Field(default="", max_length=32)  # empty = follow user message language
    default_model: str | None = None
    preferred_name: str = Field(default="", max_length=40)
    custom_instructions: str = Field(default="", max_length=1500)
    about_user: str = Field(default="", max_length=600)
    occupation: str = Field(default="", max_length=120)
    interests: list[Interest] = Field(default_factory=list, max_length=12)
    avoid_topics: str = Field(default="", max_length=400)
    expertise_level: Literal["beginner", "intermediate", "advanced", "expert"] = "intermediate"
    proactive_suggestions: bool = True


class UserProfile(BaseModel):
    user_id: str
    display_name: str = ""
    avatar_data_url: str | None = None  # small data URL only; never remote secrets
    ui_language: str = ""  # UI lang hint; independent from ai_language
    theme: str = ""  # "light" | "dark" | ""; UI store remains source of truth when empty
    ai: AIPreferences = Field(default_factory=AIPreferences)
    onboarding_completed: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ProjectPersonalization(BaseModel):
    """Optional per-request project overrides (client-owned projects)."""

    preferred_model: str | None = None
    response_style: ResponseStyle | None = None
    ai_language: str | None = None
    instructions: str | None = None
    use_personal_context: bool | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_data_url: str | None = None
    ui_language: str | None = None
    theme: str | None = None
    ai: AIPreferences | None = None
    onboarding_completed: bool | None = None
