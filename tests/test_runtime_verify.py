"""Runtime verification — real HTTP/ASGI preview probes (no fake browser)."""
from __future__ import annotations

import pytest

from app.build import store
from app.build.engine import BuildEngine
from app.build.events import clear_events_for_tests, recent_events
from app.build.runtime_verify import (
    not_available_runtime,
    runtime_to_public,
    verify_preview_http,
)
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


def test_not_available_is_explicit():
    r = not_available_runtime(reason="unit")
    pub = runtime_to_public(r)
    assert pub["runtimeVerification"] == "NOT_AVAILABLE"
    assert pub["browserInstrumentation"] == "NOT_AVAILABLE"
    assert any("NOT_AVAILABLE" in w for w in r.warnings)


@pytest.mark.asyncio
async def test_http_preview_verification_via_asgi(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    built = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="rt-1",
    )
    assert built.success and built.project_id
    # Re-probe independently
    runtime = await verify_preview_http(
        project_id=built.project_id,
        entry_file="index.html",
        preview_path=built.preview_url,
    )
    assert runtime.runtime_verification in {"HTTP_PREVIEW", "BROWSER_PREVIEW"}
    assert runtime.preview_http_status == 200
    assert runtime.html_loaded is True
    assert runtime.preview_ok is True
    assert any(a.ok for a in runtime.assets)
    assert "canvas" in runtime.elements_present or "script" in runtime.elements_present
    if runtime.runtime_verification == "BROWSER_PREVIEW":
        assert runtime.browser_instrumentation == "PLAYWRIGHT"
        assert runtime.interaction == "BROWSER"
        assert runtime.page_loaded is True
    else:
        assert runtime.browser_instrumentation == "NOT_AVAILABLE"
        assert runtime.interaction == "HTML_ASSET_PROBE"


@pytest.mark.asyncio
async def test_engine_evaluation_includes_runtime(isolated_workspace):
    engine = BuildEngine(registry=build_default_registry())
    result = await engine.run(
        "Создай игру, где машина собирает монеты",
        conversation_id="rt-2",
    )
    assert result.success
    assert result.evaluation is not None
    runtime = result.evaluation.get("runtime")
    assert runtime is not None
    assert runtime["runtimeVerification"] in {"HTTP_PREVIEW", "BROWSER_PREVIEW"}
    assert runtime["previewHttpStatus"] == 200
    if runtime["runtimeVerification"] == "BROWSER_PREVIEW":
        assert runtime["browserInstrumentation"] == "PLAYWRIGHT"
        assert runtime["pageLoaded"] is True
    else:
        assert runtime["browserInstrumentation"] == "NOT_AVAILABLE"
    types = {e.type for e in recent_events(project_id=result.project_id)}
    assert "RUNTIME_VERIFICATION_STARTED" in types
    assert "RUNTIME_VERIFICATION_COMPLETED" in types
