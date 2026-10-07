"""Build project templates — pick a minimal stack from the user request."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.build.templates.car_coins import files_for_car_coins
from app.build.templates.static_site import files_for_static_site


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


def select_blueprint(message: str) -> ProjectBlueprint:
    text = message.strip()
    if _GAME.search(text) and _CAR_COINS.search(text):
        return ProjectBlueprint(
            slug_hint="car-coins",
            title="Car Coins",
            kind="static_web",
            entry_file="index.html",
            files=files_for_car_coins(),
        )
    if _GAME.search(text):
        # Same playable stack; title generalizes if the prompt is a generic game.
        files = files_for_car_coins()
        return ProjectBlueprint(
            slug_hint="game",
            title="NEXA Game",
            kind="static_web",
            entry_file="index.html",
            files=files,
        )
    return ProjectBlueprint(
        slug_hint="site",
        title="NEXA Site",
        kind="static_web",
        entry_file="index.html",
        files=files_for_static_site(text),
    )
