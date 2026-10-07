"""BUILD_PROJECT engine V2 — real files in agent workspace."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.build import store
from app.build.engine import BuildEngine, resolve_preview_file
from app.build.events import clear_events_for_tests, recent_events
from app.build.intents import is_build_followup, is_build_new_request, is_build_request
from app.build.reality import reality_check_ready
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


def test_intent_build_vs_chat():
    assert is_build_new_request("Создай игру, где игрок управляет машиной и собирает монеты")
    assert is_build_new_request("Создай простую игру, где игрок управляет машиной и собирает монеты")
    assert is_build_new_request("Создай сайт на JavaScript")
    assert not is_build_new_request("Что такое JavaScript?")
    assert not is_build_new_request("Напиши пример JavaScript")
    assert is_build_request("добавь врагов", has_active_project=True)
    assert not is_build_request("добавь врагов", has_active_project=False)
    assert is_build_followup("сделай дизайн красивее", has_active_project=True)
    assert is_build_followup("Добавь систему очков и Game Over", has_active_project=True)


def test_understanding_car_coins():
    u = understand_request("Создай простую игру, где игрок управляет машиной и собирает монеты")
    assert u.project_type == "web_game"
    assert u.confidence >= 0.9
    assert any("машин" in x.lower() or "монет" in x.lower() for x in u.must_have + u.features)


def test_reality_check_rejects_missing(isolated_workspace):
    check = reality_check_ready(
        project_id="x",
        root_rel="builds/missing",
        entry_file="index.html",
        expected_files=["index.html"],
        tests_passed=True,
        preview_url="/api/v1/build/preview/x/index.html",
    )
    assert not check.ok


def test_preview_path_traversal(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    # no project → None
    assert resolve_preview_file("nope", "../secrets.txt") is None


@pytest.mark.asyncio
async def test_create_car_coins_game_v2(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    result = await engine.run(
        "Создай простую игру, где игрок управляет машиной и собирает монеты",
        conversation_id="conv-test-1",
    )
    assert result.success, result.error or result.message
    assert result.mode == "create"
    assert result.engine_version == "v2"
    assert result.status == "READY"
    assert result.plan is not None
    assert result.plan["status"] == "READY"
    assert result.plan["tasks"]
    assert result.project_id
    assert result.preview_url
    assert result.files_created
    assert result.root_path
    assert "chain" not in result.message.lower()
    assert "рассужд" not in result.message.lower()
    assert any(s.name == "reality_check" and s.status == "ok" for s in result.steps)

    root = Path(result.root_path)
    assert (root / "index.html").is_file()
    assert (root / "main.js").is_file()
    assert (root / "style.css").is_file()
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "canvas" in html.lower()
    assert "tabindex" in html
    js = (root / "main.js").read_text(encoding="utf-8")
    assert "coins" in js
    css = (root / "style.css").read_text(encoding="utf-8")
    assert "nexa-v2-improve" in css
    preview = resolve_preview_file(result.project_id, "index.html")
    assert preview is not None and preview.is_file()
    assert resolve_preview_file(result.project_id, "../etc/passwd") is None

    record = store.get_project(result.project_id)
    assert record is not None
    assert record.plan is not None
    assert record.status == "READY"
    assert record.stack
    assert record.preview_url
    assert record.features

    ev = recent_events(project_id=result.project_id)
    types = {e.type for e in ev}
    assert "BUILD_STARTED" in types
    assert "PLAN_CREATED" in types
    assert "PROJECT_CREATED" in types
    assert "FILE_CREATED" in types
    assert "PREVIEW_READY" in types
    assert "BUILD_COMPLETED" in types

    edit = await engine.run("добавь врагов", conversation_id="conv-test-1")
    assert edit.success, edit.error or edit.message
    assert edit.mode == "edit"
    assert edit.status == "READY"
    assert edit.project_id == result.project_id
    js2 = (root / "main.js").read_text(encoding="utf-8")
    assert "__NEXA_ENEMIES__" in js2

    score = await engine.run(
        "Добавь систему очков и Game Over", conversation_id="conv-test-1"
    )
    assert score.success, score.error or score.message
    assert score.mode == "edit"
    assert score.project_id == result.project_id
    js3 = (root / "main.js").read_text(encoding="utf-8")
    html3 = (root / "index.html").read_text(encoding="utf-8")
    assert "nexa-score-system" in js3
    assert "nexa-game-over" in js3
    assert "game-over" in html3

    pretty = await engine.run("сделай дизайн красивее", conversation_id="conv-test-1")
    assert pretty.success, pretty.error or pretty.message
    assert pretty.project_id == result.project_id
    css2 = (root / "style.css").read_text(encoding="utf-8")
    assert "nexa-pretty" in css2
