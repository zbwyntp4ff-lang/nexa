"""Request Understanding for BUILD ENGINE V2 — structured, no CoT to the user."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

ProjectType = Literal[
    "web_game",
    "static_site",
    "frontend_app",
    "backend_app",
    "mobile_app",
    "tool",
    "unknown",
]


class RequestUnderstanding(BaseModel):
    """What the user wants — filled with safe defaults when details are missing."""

    goal: str
    project_type: ProjectType = "unknown"
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    ui_ux: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    confidence: float = 0.7


_GAME = re.compile(r"(игр|game|arcade|canvas)", re.I)
_CAR = re.compile(r"(машин|car|авто|vehicle)", re.I)
_COIN = re.compile(r"(монет|coin|collect|собира)", re.I)
_ENEMY = re.compile(r"(враг|enemy|enemies|избег\w*\s+враг)", re.I)
_SITE = re.compile(r"(сайт|website|landing|лендинг|страниц)", re.I)
_APP = re.compile(r"(приложен|app|frontend|react|next|vite)", re.I)
_BACKEND = re.compile(r"(api|backend|сервер|server|fastapi|express)", re.I)
_MOBILE = re.compile(r"(мобил|mobile|android|ios|react.?native)", re.I)
_TOOL = re.compile(r"(инструмент|tool|утилита|cli|калькулятор)", re.I)
_PRETTY = re.compile(r"(красив|modern|ui|ux|дизайн|анимац)", re.I)


def understand_request(message: str) -> RequestUnderstanding:
    text = message.strip()
    lower = text.lower()

    project_type: ProjectType = "unknown"
    must_have: list[str] = []
    nice_to_have: list[str] = []
    features: list[str] = []
    ui_ux: list[str] = ["понятный интерфейс", "работает в браузере"]
    constraints: list[str] = ["минимальный стек", "реальные файлы в agent_workspace"]
    technologies: list[str] = []
    unknowns: list[str] = []

    if _GAME.search(text):
        project_type = "web_game"
        technologies = ["HTML", "CSS", "JavaScript"]
        must_have.extend(["игровой цикл", "управление", "очки/прогресс"])
        ui_ux.append("canvas или DOM-поле")
        if _CAR.search(text):
            features.append("управление машиной")
            must_have.append("машина как игрок")
        if _COIN.search(text):
            features.append("сбор монет")
            must_have.append("монеты на поле")
        if _ENEMY.search(text):
            features.append("враги")
            must_have.append("враги на поле")
        if not features:
            features.append("простая аркадная механика")
            unknowns.append("конкретная механика игры")
    elif _SITE.search(text):
        project_type = "static_site"
        technologies = ["HTML", "CSS", "JavaScript"]
        must_have.extend(["index.html", "базовая вёрстка", "preview"])
        features.append("статическая страница по запросу")
    elif _MOBILE.search(text):
        project_type = "mobile_app"
        # No mobile template in NEXA yet — degrade to static web prototype.
        technologies = ["HTML", "CSS", "JavaScript"]
        constraints.append("mobile stack отсутствует — прототип как static_web")
        unknowns.append("нативный mobile runtime")
        must_have.append("браузерный прототип")
        features.append("mobile-first layout")
    elif _BACKEND.search(text):
        project_type = "backend_app"
        technologies = ["HTML", "CSS", "JavaScript"]
        constraints.append("отдельный backend stack шаблон отсутствует — static demo")
        unknowns.append("серверный runtime")
        must_have.append("демонстрационный фронт")
        features.append("описание API в README")
    elif _APP.search(text):
        project_type = "frontend_app"
        # Prefer existing static template over inventing React/Vite scaffolding.
        technologies = ["HTML", "CSS", "JavaScript"]
        constraints.append("React/Next/Vite шаблон в Build Engine ещё не подключён — static_web")
        must_have.extend(["рабочий UI", "preview"])
        features.append("интерактивная страница")
    elif _TOOL.search(text):
        project_type = "tool"
        technologies = ["HTML", "CSS", "JavaScript"]
        must_have.append("рабочий инструмент в браузере")
        features.append("простой UI инструмента")
    else:
        project_type = "static_site"
        technologies = ["HTML", "CSS", "JavaScript"]
        must_have.append("рабочий статический проект")
        unknowns.append("точный тип продукта")

    if _PRETTY.search(text):
        nice_to_have.append("улучшенный визуальный стиль")
        ui_ux.append("аккуратная типографика и контраст")

    nice_to_have.extend(["README", "кнопка рестарта при необходимости"])

    confidence = 0.9 if project_type != "unknown" and not unknowns else 0.65
    if project_type == "web_game" and _CAR.search(text) and _COIN.search(text):
        confidence = 0.95

    goal = text if len(text) <= 200 else text[:197] + "..."
    return RequestUnderstanding(
        goal=goal,
        project_type=project_type,
        must_have=_uniq(must_have),
        nice_to_have=_uniq(nice_to_have),
        features=_uniq(features),
        ui_ux=_uniq(ui_ux),
        constraints=_uniq(constraints),
        technologies=_uniq(technologies),
        unknowns=_uniq(unknowns),
        confidence=confidence,
    )


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
