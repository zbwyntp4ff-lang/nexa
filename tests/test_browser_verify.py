"""Real Playwright browser verification tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.build import store
from app.build.browser_verify import playwright_available, verify_preview_browser
from app.build.engine import BuildEngine
from app.build.evaluation import evaluate_project
from app.build.evaluation_improve import apply_suggested_fixes
from app.build.events import clear_events_for_tests
from app.build.plan import BuildPlan
from app.build.runtime_verify import verify_preview_runtime
from app.build.understanding import understand_request
from app.tools.registry import build_default_registry

pytestmark = pytest.mark.skipif(
    not playwright_available(),
    reason="playwright not installed",
)


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


@pytest.mark.asyncio
async def test_browser_html_loads(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="br-html",
    )
    assert built.success
    br = await verify_preview_browser(project_id=built.project_id, entry_file="index.html")
    assert br.browser_available is True
    assert br.page_loaded is True
    assert br.status == "PASS"


@pytest.mark.asyncio
async def test_browser_detects_js_runtime_error(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="br-err",
    )
    assert built.success
    root = Path(built.root_path)
    main = root / "main.js"
    main.write_text(
        main.read_text(encoding="utf-8") + '\nthrow new Error("NEXA_TEST_ERROR");\n',
        encoding="utf-8",
    )
    br = await verify_preview_browser(project_id=built.project_id, entry_file="index.html")
    assert br.browser_available is True
    assert br.page_loaded is True
    assert br.status == "FAIL"
    assert br.runtime_errors or br.console_errors
    joined = " ".join(br.runtime_errors + br.console_errors)
    assert "NEXA_TEST_ERROR" in joined


@pytest.mark.asyncio
async def test_browser_detects_failed_network(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="br-net",
    )
    assert built.success
    root = Path(built.root_path)
    html_path = root / "index.html"
    html = html_path.read_text(encoding="utf-8")
    html_path.write_text(
        html.replace(
            '<script src="main.js"></script>',
            '<script src="main.js"></script><script src="missing-asset.js"></script>',
        ),
        encoding="utf-8",
    )
    br = await verify_preview_browser(project_id=built.project_id, entry_file="index.html")
    assert br.browser_available is True
    assert br.failed_requests
    assert any("missing-asset" in r for r in br.failed_requests)
    assert br.status == "FAIL"


@pytest.mark.asyncio
async def test_browser_clean_page_no_false_errors(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="br-clean",
    )
    assert built.success
    br = await verify_preview_browser(project_id=built.project_id, entry_file="index.html")
    assert br.status == "PASS"
    assert br.console_errors == []
    assert br.runtime_errors == []
    assert br.failed_requests == []


@pytest.mark.asyncio
async def test_browser_basic_interaction(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="br-ix",
    )
    assert built.success
    br = await verify_preview_browser(project_id=built.project_id, entry_file="index.html")
    assert br.interactions
    assert all(i.ok for i in br.interactions)
    assert any(i.name.startswith("click") for i in br.interactions)
    assert any(i.name == "keyboard_arrows" for i in br.interactions)


@pytest.mark.asyncio
async def test_auto_repair_js_error_then_pass(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="br-repair",
    )
    assert built.success
    root = Path(built.root_path)
    main = root / "main.js"
    broken = main.read_text(encoding="utf-8") + '\nthrow new Error("NEXA_TEST_ERROR");\n'
    main.write_text(broken, encoding="utf-8")

    runtime = await verify_preview_runtime(
        project_id=built.project_id,
        entry_file="index.html",
        preview_path=built.preview_url,
        enable_browser=True,
    )
    assert runtime.runtime_verification == "BROWSER_PREVIEW"
    assert runtime.runtime_errors or runtime.console_errors

    u = understand_request("Создай игру, где машина собирает монеты")
    plan = BuildPlan(
        project_id=built.project_id,
        name="Car",
        type="web_game",
        goal=u.goal,
        requirements=list(u.must_have),
        features=list(u.features),
        files=["index.html", "main.js", "style.css", "README.md"],
        understanding=u,
        entry_file="index.html",
        preview=built.preview_url,
    )
    files = {
        "index.html": (root / "index.html").read_text(encoding="utf-8"),
        "main.js": broken,
        "style.css": (root / "style.css").read_text(encoding="utf-8"),
        "README.md": (root / "README.md").read_text(encoding="utf-8"),
    }
    ev = evaluate_project(
        user_request=plan.goal,
        plan=plan,
        files=files,
        preview_ok=False,
        tests_passed=True,
        runtime_result=runtime,
    )
    assert ev.status in {"NEEDS_IMPROVEMENT", "FAIL"}
    assert "fix_js_runtime_error" in ev.suggested_fixes

    fixed, notes = apply_suggested_fixes(files, ev.suggested_fixes)
    assert "fix_js_runtime_error" in notes
    assert "NEXA_TEST_ERROR" not in fixed["main.js"]
    main.write_text(fixed["main.js"], encoding="utf-8")

    runtime2 = await verify_preview_runtime(
        project_id=built.project_id,
        entry_file="index.html",
        preview_path=built.preview_url,
        enable_browser=True,
    )
    assert runtime2.status == "PASS"
    assert not runtime2.runtime_errors
    assert "NEXA_TEST_ERROR" not in (root / "main.js").read_text(encoding="utf-8")
