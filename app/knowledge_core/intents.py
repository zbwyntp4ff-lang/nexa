"""Lightweight intent detection for Knowledge Core pack selection."""
from __future__ import annotations

import re

from app.knowledge_core.models import IntentKind

_PATTERNS: list[tuple[IntentKind, re.Pattern[str]]] = [
    (
        IntentKind.BUILD,
        re.compile(
            r"(создай|сделай|собери|напиши)\s+(мне\s+)?(игру|сайт|приложен|инструмент|прототип|api|бот)|"
            r"create\s+(an?\s+)?(app|game|website|site|tool|prototype)|"
            r"build\s+(an?\s+)?(app|game|website|site)|"
            r"полный\s+проект|working\s+project",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.SHADOW,
        re.compile(
            r"что\s+я\s+упустил|что\s+пропустил|скрыт|blind\s*spot|shadow|"
            r"what\s+(did\s+i\s+)?miss|hidden\s+constraint",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.FORGE,
        re.compile(
            r"объедини|скомбиниру|скрести|forge|combine\s+(these\s+)?ideas|"
            r"merge\s+(these\s+)?ideas|соедини\s+иде",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.BREAKTHROUGH,
        re.compile(
            r"неожиданн|breakthrough|distant\s+connection|удалённ.*(связ|иде)|"
            r"unexpected\s+connection",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.RESEARCH,
        re.compile(
            r"исследуй|исследование|research|гипотез|доказательств|omniverse|"
            r"best\s+path|эксперимент",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.DESIGN,
        re.compile(
            r"\bui\b|\bux\b|дизайн|typography|accessibility|layout|"
            r"responsive|дизайн[\-\s]?систем",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.CODE,
        re.compile(
            r"\b(code|coding|bug|refactor|typescript|javascript|python|react|"
            r"next\.?js|sql|docker|git)\b|код|баг|рефактор|функци",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.SEARCH,
        re.compile(
            r"актуальн|сегодня|сейчас|latest|current\s+price|на\s+сегодня|"
            r"проверь\s+в\s+интернет|search\s+the\s+web|найди\s+в\s+интернет|"
            r"поиск\s+в\s+интернет|новост",
            re.IGNORECASE,
        ),
    ),
    (
        IntentKind.CAPABILITY,
        re.compile(
            r"что\s+ты\s+умеешь|на\s+что\s+ты\s+способ|what\s+can\s+you\s+do",
            re.IGNORECASE,
        ),
    ),
]


def detect_intents(text: str) -> list[IntentKind]:
    found: list[IntentKind] = []
    for kind, pattern in _PATTERNS:
        if pattern.search(text) and kind not in found:
            found.append(kind)
    if not found:
        found.append(IntentKind.GENERAL)
    return found
