"""BUILD_PROJECT intent detection — shared by API and BuildEngine."""
from __future__ import annotations

import re

_BUILD_NEW = re.compile(
    r"(создай|сделай|собери|напиши)\s+(мне\s+)?"
    r"(?:\S+\s+){0,4}"
    r"(игру|игрушку|сайт|приложен\w*|инструмент|прототип|программ\w*|проект|api|бот)|"
    r"create\s+(an?\s+|me\s+a\s+)?(?:\S+\s+){0,4}(app|game|website|site|tool|prototype|program|project)|"
    r"build\s+(an?\s+|me\s+a\s+)?(?:\S+\s+){0,4}(app|game|website|site|tool|project)|"
    r"(сделай|создай)\s+мне\b|"
    r"и\s+запусти|"
    r"working\s+project|полный\s+проект",
    re.IGNORECASE,
)

_BUILD_FOLLOWUP = re.compile(
    r"^(добавь|измени|исправь|улучши|"
    r"сделай(?:\s+\S+){0,4}\s+(красивее|быстрее|больше)|"
    r"add\s+|change\s+|fix\s+|improve\s+|make\s+(it\s+)?|"
    r"поменяй|увеличь|уменьши|перепиши)|"
    r"(game\s*over|систем\w*\s+очк|очк\w*|score)",
    re.IGNORECASE,
)

_CODE_SAMPLE_ONLY = re.compile(
    r"(пример\s+код|sample\s+code|example\s+(of\s+)?code|snippet|"
    r"как\s+написать|how\s+to\s+write|объясни\s+код)",
    re.IGNORECASE,
)


def is_build_new_request(text: str) -> bool:
    stripped = text.strip()
    if not stripped or _CODE_SAMPLE_ONLY.search(stripped):
        return False
    return bool(_BUILD_NEW.search(stripped))


def is_build_followup(text: str, *, has_active_project: bool) -> bool:
    if not has_active_project:
        return False
    stripped = text.strip()
    if is_build_new_request(stripped):
        return False
    return bool(_BUILD_FOLLOWUP.search(stripped))


def is_build_request(text: str, *, has_active_project: bool = False) -> bool:
    return is_build_new_request(text) or is_build_followup(text, has_active_project=has_active_project)
