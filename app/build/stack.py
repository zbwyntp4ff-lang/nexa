"""Stack selection — reuse existing NEXA build templates only."""
from __future__ import annotations

from dataclasses import dataclass

from app.build.templates import ProjectBlueprint, is_three_slug, select_blueprint
from app.build.understanding import RequestUnderstanding


@dataclass(frozen=True)
class StackChoice:
    """Selected stack + concrete blueprint from existing templates."""

    stack_id: str
    label: str
    architecture: str
    dependencies: list[str]
    commands: list[str]
    tests: list[str]
    blueprint: ProjectBlueprint
    reason: str


def select_stack(message: str, understanding: RequestUnderstanding) -> StackChoice:
    """
    Pick the lightest existing template that can deliver the request.

    Principle: do not invent React/Next/Vite/mobile scaffolds if NEXA has no
    Build Engine template for them yet — degrade to the working static_web stack.
    """
    blueprint = select_blueprint(message)
    ptype = understanding.project_type

    if is_three_slug(blueprint.slug_hint):
        return StackChoice(
            stack_id="threejs-cdn-game",
            label="HTML / CSS / JS (Three.js CDN 3D)",
            architecture="static_web",
            dependencies=["three@0.160 (CDN)"],
            commands=[],
            tests=[
                "entry HTML exists",
                "main.js contains THREE / WebGLRenderer / game loop",
                "scene.json present",
                "preview serves index.html",
            ],
            blueprint=blueprint,
            reason="3D веб-игра → Three.js CDN шаблон Build Engine",
        )

    if ptype == "web_game" or blueprint.kind == "static_web" and blueprint.slug_hint in {
        "car-coins",
        "game",
    }:
        return StackChoice(
            stack_id="html-css-js-game",
            label="HTML / CSS / JS (canvas game)",
            architecture="static_web",
            dependencies=[],
            commands=[],
            tests=[
                "entry HTML exists",
                "main.js contains game loop",
                "preview serves index.html",
            ],
            blueprint=blueprint,
            reason="простая веб-игра → существующий HTML/CSS/JS шаблон",
        )

    # frontend_app / mobile / backend: no dedicated scaffolds yet → static_web
    if ptype in {"frontend_app", "mobile_app", "backend_app", "tool", "static_site", "unknown"}:
        return StackChoice(
            stack_id="html-css-js",
            label="HTML / CSS / JS (static)",
            architecture="static_web",
            dependencies=[],
            commands=[],
            tests=[
                "entry HTML exists",
                "linked assets readable",
                "preview serves entry",
            ],
            blueprint=blueprint,
            reason="подходящий минимальный существующий шаблон static_web",
        )

    return StackChoice(
        stack_id="html-css-js",
        label="HTML / CSS / JS (static)",
        architecture="static_web",
        dependencies=[],
        commands=[],
        tests=["entry HTML exists"],
        blueprint=blueprint,
        reason="fallback на существующий static_web",
    )
