"""Build project templates — pick a minimal stack from the user request."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.build.templates.car_coins import files_for_car_coins
from app.build.templates.static_site import files_for_static_site
from app.build.templates.three_adventure import files_for_three_adventure
from app.build.templates.three_flight import files_for_three_flight
from app.build.templates.three_racing import files_for_three_racing
from app.build.templates.three_tank import files_for_three_tank


@dataclass(frozen=True)
class ProjectBlueprint:
    slug_hint: str
    title: str
    kind: str  # static_web
    entry_file: str
    files: dict[str, str]


_CAR_COINS = re.compile(
    r"(машин|car|монет|coin|collect|собира)",
    re.IGNORECASE,
)
_GAME = re.compile(r"(игр|game)", re.IGNORECASE)
_THREE_D = re.compile(
    r"(3\s*d|three\.?js|webgl|трёхмер|трехмер|объ[её]мн)",
    re.IGNORECASE,
)
_RACING = re.compile(r"(гонк|racing|race|трек|track|дрифт|drift)", re.IGNORECASE)
_FLIGHT = re.compile(r"(пол[её]т|flight|самол[её]т|plane|авиа|fly)", re.IGNORECASE)
_TANK = re.compile(r"(танк|tank|танков)", re.IGNORECASE)
_ADVENTURE = re.compile(
    r"(приключ|adventure|квест|quest|исследова|explore|портал|portal|кристалл|gem)",
    re.IGNORECASE,
)

_THREE_SLUGS = frozenset({"three-racing", "three-flight", "three-tank", "three-adventure"})


def is_three_slug(slug: str) -> bool:
    return slug in _THREE_SLUGS


def _three(slug: str, title: str, files: dict[str, str]) -> ProjectBlueprint:
    return ProjectBlueprint(
        slug_hint=slug,
        title=title,
        kind="static_web",
        entry_file="index.html",
        files=files,
    )


def _pick_three_genre(text: str) -> ProjectBlueprint | None:
    """Pick a Three.js template when genre cues (or generic 3D) are present."""
    if _FLIGHT.search(text):
        return _three("three-flight", "NEXA Flight 3D", files_for_three_flight())
    if _TANK.search(text):
        return _three("three-tank", "NEXA Tank 3D", files_for_three_tank())
    if _ADVENTURE.search(text):
        return _three("three-adventure", "NEXA Adventure 3D", files_for_three_adventure())
    if _RACING.search(text):
        return _three("three-racing", "NEXA Racing 3D", files_for_three_racing())
    return None


def select_blueprint(message: str) -> ProjectBlueprint:
    text = message.strip()
    is_game = bool(_GAME.search(text))
    wants_3d = bool(_THREE_D.search(text))
    has_genre = bool(
        _RACING.search(text)
        or _FLIGHT.search(text)
        or _TANK.search(text)
        or _ADVENTURE.search(text)
    )

    # 3D / Three.js game prompts (genre-specific or default racing)
    if wants_3d or (is_game and has_genre):
        picked = _pick_three_genre(text)
        if picked is not None:
            return picked
        if wants_3d:
            return _three("three-racing", "NEXA Racing 3D", files_for_three_racing())

    # Classic 2D canvas car/coins (and generic 2D game)
    if is_game and _CAR_COINS.search(text):
        return ProjectBlueprint(
            slug_hint="car-coins",
            title="Car Coins",
            kind="static_web",
            entry_file="index.html",
            files=files_for_car_coins(),
        )
    if is_game:
        return ProjectBlueprint(
            slug_hint="game",
            title="NEXA Game",
            kind="static_web",
            entry_file="index.html",
            files=files_for_car_coins(),
        )
    return ProjectBlueprint(
        slug_hint="site",
        title="NEXA Site",
        kind="static_web",
        entry_file="index.html",
        files=files_for_static_site(text),
    )
