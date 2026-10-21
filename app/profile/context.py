"""Compact personalization hint for AI — intentionally short (latency/tokens)."""
from __future__ import annotations

from app.profile.models import AIPreferences, ProjectPersonalization, ResponseStyle, UserProfile

_STYLE_HINTS: dict[ResponseStyle, str] = {
    "concise": "Be concise; prefer short answers.",
    "balanced": "Balance brevity and clarity.",
    "detailed": "Provide more detail when useful.",
    "technical": "Prefer precise technical wording.",
}

_PERSONALITY_HINTS = {
    "professional": "Tone: professional.",
    "friendly": "Tone: friendly.",
    "direct": "Tone: direct.",
    "technical": "Tone: technical.",
}


def build_compact_hint(
    profile: UserProfile,
    project: ProjectPersonalization | None = None,
) -> str | None:
    """Return a short system hint or None when personalization is off.

    Never includes email, passwords, API keys, or internal memory dumps.
    """
    ai = profile.ai
    use_ctx = ai.personalization_enabled
    if project and project.use_personal_context is False:
        use_ctx = False
    if project and project.use_personal_context is True:
        use_ctx = True
    if not use_ctx:
        return None

    style: ResponseStyle = project.response_style if project and project.response_style else ai.response_style
    parts: list[str] = ["Personalization:"]
    parts.append(_STYLE_HINTS.get(style, _STYLE_HINTS["balanced"]))
    parts.append(_PERSONALITY_HINTS.get(ai.personality, _PERSONALITY_HINTS["friendly"]))

    if ai.brevity == "low":
        parts.append("Keep answers short.")
    elif ai.brevity == "high":
        parts.append("Allow longer answers when needed.")

    if ai.detail_level == "low":
        parts.append("Low detail.")
    elif ai.detail_level == "high":
        parts.append("Higher detail when helpful.")

    if ai.answer_format == "bullets":
        parts.append("Prefer bullet lists when suitable.")
    elif ai.answer_format == "structured":
        parts.append("Prefer structured sections when suitable.")
    elif ai.answer_format == "prose":
        parts.append("Prefer prose.")

    lang = (project.ai_language if project and project.ai_language else ai.ai_language or "").strip()
    if lang:
        parts.append(f"Reply language preference: {lang[:32]}.")

    name = (ai.preferred_name or profile.display_name or "").strip()
    if name:
        parts.append(f"Address user as {name[:40]}.")

    if project and project.instructions and project.instructions.strip():
        # Cap project instructions to keep prompt small.
        instr = " ".join(project.instructions.strip().split())
        parts.append(f"Project: {instr[:160]}")

    text = " ".join(parts)
    return text[:420] if text else None


def resolve_preferred_model(
    profile: UserProfile,
    project: ProjectPersonalization | None = None,
) -> str | None:
    if project and project.preferred_model:
        return project.preferred_model.strip() or None
    if profile.ai.default_model:
        return profile.ai.default_model.strip() or None
    return None
