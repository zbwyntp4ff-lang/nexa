"""Evaluation Engine V1 — intent scoring + improvement loop."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.build import store
from app.build.engine import BuildEngine
from app.build.evaluation import evaluate_project, evaluation_to_public
from app.build.evaluation_improve import apply_suggested_fixes
from app.build.events import clear_events_for_tests, recent_events
from app.build.plan import BuildPlan
from app.build.templates.car_coins import files_for_car_coins
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


def _plan_for(message: str, files: dict[str, str]) -> BuildPlan:
    u = understand_request(message)
    return BuildPlan(
        project_id="eval-test",
        name="Test",
        type=u.project_type,
        goal=u.goal,
        requirements=list(u.must_have),
        features=list(u.features),
        files=list(files.keys()),
        understanding=u,
        entry_file="index.html",
    )


@pytest.mark.asyncio
async def test1_car_coins_evaluation_pass(isolated_workspace):
    """TEST 1: car + coins game builds and evaluation PASSes."""
    engine = BuildEngine(registry=build_default_registry())
    msg = "Создай игру, где машина собирает монеты"
    result = await engine.run(msg, conversation_id="eval-t1")
    assert result.success, result.error or result.message
    assert result.status == "READY"
    assert result.evaluation is not None
    assert result.evaluation["status"] == "PASS"
    assert result.evaluation["score"] >= 70
    root = Path(result.root_path)
    js = (root / "main.js").read_text(encoding="utf-8")
    assert "car" in js and "coins" in js and "requestAnimationFrame" in js
    assert result.improvement_attempts == 0  # TEST 4 overlap: no needless rewrite
    rt = result.evaluation.get("runtime") or {}
    assert rt.get("runtimeVerification") in {"HTTP_PREVIEW", "BROWSER_PREVIEW"}
    if rt.get("runtimeVerification") == "BROWSER_PREVIEW":
        assert rt.get("browserInstrumentation") == "PLAYWRIGHT"
        assert rt.get("browserAvailable") is True
        assert rt.get("pageLoaded") is True
    else:
        assert rt.get("browserInstrumentation") == "NOT_AVAILABLE"
    types = {e.type for e in recent_events(project_id=result.project_id)}
    assert "EVALUATION_STARTED" in types
    assert "EVALUATION_COMPLETED" in types
    assert "RUNTIME_VERIFICATION_COMPLETED" in types
    assert "IMPROVEMENT_STARTED" not in types


@pytest.mark.asyncio
async def test2_car_coins_enemies_evaluation(isolated_workspace):
    """TEST 2: enemies required → evaluation/improvement enables them."""
    engine = BuildEngine(registry=build_default_registry())
    msg = "Создай игру с машиной, монетами и врагами"
    result = await engine.run(msg, conversation_id="eval-t2")
    assert result.success, result.error or result.message
    assert result.status == "READY"
    assert result.evaluation is not None
    assert result.evaluation["status"] == "PASS"
    js = Path(result.root_path).joinpath("main.js").read_text(encoding="utf-8")
    assert "car" in js and "coins" in js
    assert "__NEXA_ENEMIES__" in js
    assert any(x in js for x in ("__NEXA_ENEMIES__ = 3", "__NEXA_ENEMIES__ || 3"))
    # improvement loop should have run at least once for enemies
    types = {e.type for e in recent_events(project_id=result.project_id)}
    assert "EVALUATION_COMPLETED" in types
    assert "IMPROVEMENT_STARTED" in types or result.improvement_attempts >= 1


def test3_controlled_missing_feature_triggers_improve(isolated_workspace):
    """TEST 3: incomplete project → evaluation fails → suggested fix → improve."""
    # Controlled incomplete: full template but coins logic removed from JS
    files = files_for_car_coins()
    files["main.js"] = (
        "const canvas = document.getElementById('game');\n"
        "const car = { x: 1 };\n"
        "function loop(){ requestAnimationFrame(loop); }\n"
        "window.addEventListener('keydown', (e) => { if (e.key === 'r') location.reload(); });\n"
        "loop();\n"
    )
    files["README.md"] = "# Game\n"
    msg = "Создай игру, где машина собирает монеты"
    plan = _plan_for(msg, files)
    ev = evaluate_project(
        user_request=msg,
        plan=plan,
        files=files,
        preview_ok=True,
        tests_passed=True,
        pass_threshold=70,
    )
    assert ev.status in {"NEEDS_IMPROVEMENT", "FAIL"}, (ev.status, ev.passed, ev.failed)
    assert any("Монет" in f or "монет" in f.lower() for f in ev.failed)
    assert "add_coins" in ev.suggested_fixes

    # Enemies disabled in template → detect + improve → PASS
    files2 = files_for_car_coins()
    msg2 = "Создай игру с машиной, монетами и врагами"
    plan2 = _plan_for(msg2, files2)
    ev2 = evaluate_project(
        user_request=msg2,
        plan=plan2,
        files=files2,
        preview_ok=True,
        tests_passed=True,
    )
    assert ev2.status == "NEEDS_IMPROVEMENT"
    assert "enable_enemies" in ev2.suggested_fixes
    fixed, notes = apply_suggested_fixes(files2, ev2.suggested_fixes)
    assert "enable_enemies" in notes
    ev3 = evaluate_project(
        user_request=msg2,
        plan=plan2,
        files=fixed,
        preview_ok=True,
        tests_passed=True,
    )
    assert ev3.status == "PASS"
    assert ev3.score >= 70


@pytest.mark.asyncio
async def test4_successful_project_not_rewritten(isolated_workspace):
    """TEST 4: PASS project does not enter improvement loop."""
    engine = BuildEngine(registry=build_default_registry())
    result = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="eval-t4",
    )
    assert result.success
    assert result.evaluation["status"] == "PASS"
    assert result.improvement_attempts == 0
    improve_events = [
        e for e in recent_events(project_id=result.project_id) if e.type == "IMPROVEMENT_STARTED"
    ]
    assert improve_events == []
