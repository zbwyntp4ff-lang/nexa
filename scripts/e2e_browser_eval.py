"""E2E: car+coins+enemies with real Playwright browser + controlled JS repair."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from app.build import store
from app.build.browser_verify import playwright_available
from app.build.engine import BuildEngine
from app.build.evaluation import evaluate_project
from app.build.evaluation_improve import apply_suggested_fixes
from app.build.events import clear_events_for_tests, recent_events
from app.build.plan import BuildPlan
from app.build.runtime_verify import verify_preview_runtime
from app.build.understanding import understand_request
from app.config.settings import get_settings
from app.tools.registry import build_default_registry, get_default_tool_registry


async def main() -> None:
    report = {
        "browser_runtime": "NO",
        "page_load": "FAIL",
        "console_monitoring": "FAIL",
        "runtime_errors": "FAIL",
        "network_errors": "FAIL",
        "interaction": "FAIL",
        "auto_repair": "FAIL",
        "ready": "FAIL",
        "tests": "see pytest",
    }

    if not playwright_available():
        print(json.dumps(report, indent=2))
        print("E2E_BROWSER_FAIL: playwright not available")
        raise SystemExit(1)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        import os

        os.environ["AGENT_WORKSPACE_DIR"] = str(tmp_path / "ws")
        get_settings.cache_clear()
        store._STORE = tmp_path / "build_projects.json"  # noqa: SLF001
        get_default_tool_registry.cache_clear()
        clear_events_for_tests()

        engine = BuildEngine(registry=build_default_registry())
        msg = "Создай игру, где машина собирает монеты и избегает врагов"
        built = await engine.run(msg, conversation_id="e2e-browser-game")

        print("BUILD", built.success, built.status, built.preview_url)
        assert built.success, built.message
        assert built.status == "READY"
        assert built.preview_url
        report["ready"] = "PASS"

        # Prefer live re-verify for honest browser fields
        runtime = await verify_preview_runtime(
            project_id=built.project_id,
            entry_file="index.html",
            preview_path=built.preview_url,
            enable_browser=True,
        )
        print(
            "RUNTIME",
            runtime.runtime_verification,
            runtime.browser_instrumentation,
            runtime.status,
            "page=",
            runtime.page_loaded,
            "browser=",
            runtime.browser_available,
        )
        assert runtime.runtime_verification == "BROWSER_PREVIEW"
        assert runtime.browser_instrumentation == "PLAYWRIGHT"
        assert runtime.browser_available is True
        report["browser_runtime"] = "YES"

        assert runtime.page_loaded and runtime.html_loaded
        report["page_load"] = "PASS"

        # Console monitoring supported (list present, no errors on clean game)
        assert isinstance(runtime.console_errors, list)
        assert not runtime.console_errors
        report["console_monitoring"] = "PASS"

        assert isinstance(runtime.runtime_errors, list)
        assert not runtime.runtime_errors
        report["runtime_errors"] = "PASS"

        assert isinstance(runtime.failed_requests, list)
        assert not runtime.failed_requests
        report["network_errors"] = "PASS"

        assert runtime.interaction == "BROWSER"
        assert any(i.get("ok") for i in runtime.interactions)
        report["interaction"] = "PASS"

        js = Path(built.root_path).joinpath("main.js").read_text(encoding="utf-8")
        assert "car" in js.lower() or "player" in js.lower()
        assert "coin" in js.lower()
        assert "__NEXA_ENEMIES__" in js
        assert "NEXA_TEST_ERROR" not in js

        ev_types = {e.type for e in recent_events(project_id=built.project_id, limit=200)}
        print("EVENTS", sorted(ev_types))
        assert "RUNTIME_VERIFICATION_STARTED" in ev_types
        assert "RUNTIME_VERIFICATION_COMPLETED" in ev_types
        assert "EVALUATION_COMPLETED" in ev_types
        assert built.evaluation and built.evaluation.get("status") == "PASS"

        # Controlled JS error → detect → fix → browser pass; leave clean
        root = Path(built.root_path)
        main = root / "main.js"
        original = main.read_text(encoding="utf-8")
        main.write_text(original + '\nthrow new Error("NEXA_TEST_ERROR");\n', encoding="utf-8")

        broken_rt = await verify_preview_runtime(
            project_id=built.project_id,
            entry_file="index.html",
            preview_path=built.preview_url,
            enable_browser=True,
        )
        print(
            "BROKEN",
            broken_rt.status,
            "runtime_errors=",
            broken_rt.runtime_errors,
            "console=",
            broken_rt.console_errors,
        )
        assert broken_rt.runtime_errors or broken_rt.console_errors

        u = understand_request(msg)
        plan = BuildPlan(
            project_id=built.project_id,
            name="Car Coins",
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
            "main.js": main.read_text(encoding="utf-8"),
            "style.css": (root / "style.css").read_text(encoding="utf-8"),
            "README.md": (root / "README.md").read_text(encoding="utf-8"),
        }
        ev = evaluate_project(
            user_request=msg,
            plan=plan,
            files=files,
            preview_ok=False,
            tests_passed=True,
            runtime_result=broken_rt,
        )
        print("EVAL_BROKEN", ev.status, ev.suggested_fixes)
        assert "fix_js_runtime_error" in ev.suggested_fixes

        fixed, notes = apply_suggested_fixes(files, ev.suggested_fixes)
        assert "fix_js_runtime_error" in notes
        assert "NEXA_TEST_ERROR" not in fixed["main.js"]
        main.write_text(fixed["main.js"], encoding="utf-8")

        fixed_rt = await verify_preview_runtime(
            project_id=built.project_id,
            entry_file="index.html",
            preview_path=built.preview_url,
            enable_browser=True,
        )
        print("FIXED", fixed_rt.status, fixed_rt.runtime_errors)
        assert fixed_rt.status == "PASS"
        assert not fixed_rt.runtime_errors
        assert "NEXA_TEST_ERROR" not in main.read_text(encoding="utf-8")
        report["auto_repair"] = "PASS"

        get_settings.cache_clear()
        get_default_tool_registry.cache_clear()
        clear_events_for_tests()

    print("--- FINAL REPORT ---")
    print(f"Browser runtime: {report['browser_runtime']}")
    print(f"Page load: {report['page_load']}")
    print(f"Console monitoring: {report['console_monitoring']}")
    print(f"Runtime errors: {report['runtime_errors']}")
    print(f"Network errors: {report['network_errors']}")
    print(f"Interaction: {report['interaction']}")
    print(f"Auto repair: {report['auto_repair']}")
    print("E2E_BROWSER_OK")


if __name__ == "__main__":
    asyncio.run(main())
