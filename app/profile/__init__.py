"""Part 11 — user profiles and personalization."""
from app.profile.models import AIPreferences, ProjectPersonalization, UserProfile
from app.profile.service import ProfileService

__all__ = [
    "AIPreferences",
    "ProjectPersonalization",
    "ProfileService",
    "UserProfile",
]
