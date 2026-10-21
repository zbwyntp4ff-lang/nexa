"""Part 13 — Three.js Game Creator (templates, eval, preview CSP, export)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.build import store
from app.build.engine import BuildEngine, resolve_preview_file
from app.build.events import clear_events_for_tests
from app.build.templates import is_three_slug, select_blueprint
from app.build.understanding import understand_request
from app.tools.registry import build_default_registry


@pytest.fixture()
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path / "ws"))
    from app.config.settings import get_settings

    get_settings.cache_clear()
    store._STORE = tmp_path / "build_projects.json"  # noqa: SLF001
    from app.tools.registry import get_default_tool_registry

    get_default_tool_registry.cache_clear()
    clear_events_for_tests()
    yield tmp_path
    get_settings.cache_clear()
    get_default_tool_registry.cache_clear()
    clear_events_for_tests()


def test_select_three_racing():
    bp = select_blueprint("Создай 3D гонку на Three.js")
    assert is_three_slug(bp.slug_hint)
    assert bp.slug_hint == "three-racing"
    assert "THREE" in bp.files["main.js"] or "WebGLRenderer" in bp.files["main.js"]
    assert "scene.json" in bp.files
    assert "cdn.jsdelivr.net/npm/three@" in bp.files["index.html"]


def test_select_three_genres():
    assert select_blueprint("создай 3d игру про полёт").slug_hint == "three-flight"
    assert select_blueprint("создай игру с танками 3d").slug_hint == "three-tank"
    assert select_blueprint("создай 3d приключение с порталом").slug_hint == "three-adventure"


def test_car_coins_still_2d_without_3d():
    bp = select_blueprint("Создай простую игру, где игрок управляет машиной и собирает монеты")
    assert bp.slug_hint == "car-coins"
    assert "THREE" not in bp.files["main.js"]


def test_understanding_three_racing():
    u = understand_request("Создай 3D гонку")
    assert u.project_type == "web_game"
    assert any("Three" in t or "three" in t.lower() for t in u.technologies) or any(
        "3d" in f.lower() or "гонк" in f.lower() for f in u.features
    )


@pytest.mark.asyncio
async def test_create_three_racing_and_export(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    result = await engine.run(
        "Создай 3D гонку на Three.js",
        conversation_id="conv-3d-1",
    )
    assert result.success, result.error or result.message
    assert result.project_id
    assert result.preview_url
    root = Path(result.root_path)
    js = (root / "main.js").read_text(encoding="utf-8")
    assert "WebGLRenderer" in js
    assert "requestAnimationFrame" in js
    assert (root / "scene.json").is_file()
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "three@" in html
    assert resolve_preview_file(result.project_id, "index.html") is not None
    assert resolve_preview_file(result.project_id, "../etc/passwd") is None

    from app.main import app

    client = TestClient(app)
    preview = client.get(f"/api/v1/build/preview/{result.project_id}/index.html")
    assert preview.status_code == 200
    csp = preview.headers.get("content-security-policy", "")
    assert "cdn.jsdelivr.net" in csp
    assert "script-src" in csp

    export = client.get(f"/api/v1/build/export/{result.project_id}")
    assert export.status_code == 200
    assert export.headers.get("content-type", "").startswith("application/zip")
    assert len(export.content) > 100

    meta = client.get(f"/api/v1/build/projects/{result.project_id}")
    assert meta.status_code == 200
    assert "scene.json" in meta.json()["files"]

    edit = await engine.run("добавь соперников", conversation_id="conv-3d-1")
    assert edit.success, edit.error or edit.message
