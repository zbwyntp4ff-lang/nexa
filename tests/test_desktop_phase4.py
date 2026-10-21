"""Phase 4 — browser, local files, open_result, locality, path allowlist."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.tools.desktop.locality import clear_locality_cache, is_local_desktop, require_local_desktop
from app.tools.desktop.local_files import LocalFileTool
from app.tools.desktop.open_result import OpenResultTool, probe_default_handlers
from app.tools.desktop.paths import resolve_allowed_path
from app.tools.office.result_store import ResultStore
from app.models.errors import PathTraversalError


@pytest.fixture(autouse=True)
def _local_desktop_env(monkeypatch):
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "1")
    clear_locality_cache()
    yield
    clear_locality_cache()


def test_locality_respects_flag(monkeypatch):
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "0")
    clear_locality_cache()
    assert is_local_desktop() is False
    assert require_local_desktop("x") is not None
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "1")
    clear_locality_cache()
    assert is_local_desktop() is True


def test_path_allowlist_blocks_escape(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "ok.txt").write_text("hi", encoding="utf-8")
    ok = resolve_allowed_path("ok.txt", roots=[root.resolve()], must_exist=True)
    assert ok.name == "ok.txt"
    with pytest.raises(PathTraversalError):
        resolve_allowed_path("../ok.txt", roots=[root.resolve()], must_exist=False)
    # Absolute path outside root
    outside = tmp_path / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(PathTraversalError):
        resolve_allowed_path(str(outside), roots=[root.resolve()], must_exist=True)


@pytest.mark.asyncio
async def test_local_files_create_list_read(tmp_path):
    tool = LocalFileTool(tmp_path)
    created = await tool.execute(action="write_new", path="notes/hello.txt", content="hello nexa")
    assert created.success, created.error
    listed = await tool.execute(action="list", path="notes")
    assert listed.success
    assert any(e["name"] == "hello.txt" for e in listed.output["entries"])
    read = await tool.execute(action="read", path="notes/hello.txt")
    assert read.success
    assert "hello nexa" in read.output["text"]


@pytest.mark.asyncio
async def test_local_files_delete_requires_confirm(tmp_path):
    tool = LocalFileTool(tmp_path)
    await tool.execute(action="write_new", path="todelete.txt", content="x")
    denied = await tool.execute(action="delete", path="todelete.txt")
    assert not denied.success
    assert denied.metadata.get("needs_confirmation")
    assert (tmp_path / "todelete.txt").exists()
    ok = await tool.execute(action="delete", path="todelete.txt", confirm=True)
    assert ok.success
    assert not (tmp_path / "todelete.txt").exists()


@pytest.mark.asyncio
async def test_local_files_refused_when_remote(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "0")
    clear_locality_cache()
    tool = LocalFileTool(tmp_path)
    result = await tool.execute(action="list", path=".")
    assert not result.success
    assert "NEXA_LOCAL_DESKTOP" in (result.error or "")


@pytest.mark.asyncio
async def test_scaffold_project(tmp_path):
    tool = LocalFileTool(tmp_path)
    result = await tool.execute(
        action="scaffold_project",
        path="projects/demo",
        readme="# Demo\n\n- file: /api/v1/results/x/download\n",
    )
    assert result.success, result.error
    assert (tmp_path / "projects" / "demo" / "README.md").is_file()


@pytest.mark.asyncio
async def test_open_result_requires_confirm_and_local(tmp_path):
    store = ResultStore(tmp_path)
    rec = store.save_bytes(
        b"%PDF-1.4 fake but enough bytes for store check......." + b"0" * 200,
        filename="doc.pdf",
        media_type="application/pdf",
        extension="pdf",
        task_id="t1",
    )
    tool = OpenResultTool(tmp_path, store=store)
    denied = await tool.execute(file_id=rec.file_id)
    assert not denied.success
    assert denied.metadata.get("needs_confirmation")


def test_probe_handlers_honest():
    info = probe_default_handlers(".pptx")
    assert "platform" in info
    assert "candidates" in info
    # Must not invent a path that does not exist.
    for c in info["candidates"]:
        assert Path(c).is_file()


@pytest.mark.asyncio
async def test_browser_ssrf_blocked():
    from app.tools.desktop.browser_tool import BrowserTool

    tool = BrowserTool(Path("."))
    result = await tool.execute(action="open", url="http://127.0.0.1:8420/health")
    assert not result.success
    assert result.metadata.get("status") == "ssrf_blocked" or "SSRF" in (result.error or "") or "private" in (
        result.error or ""
    ).lower() or "localhost" in (result.error or "").lower() or "Invalid" in (result.error or "") or "blocked" in (
        result.error or ""
    ).lower()


@pytest.mark.asyncio
async def test_browser_confirm_for_submit_click(tmp_path):
    from app.tools.desktop.browser_tool import BrowserTool

    tool = BrowserTool(tmp_path)
    # Even before playwright launch — confirmation gate fires first for significant selectors.
    # Use a public URL shape; confirm gate runs after URL validate — example.com is fine.
    result = await tool.execute(
        action="click",
        url="https://example.com",
        selector="button[type=submit]",
        confirm=False,
    )
    # May fail earlier if playwright missing — still must not claim click succeeded.
    assert not result.success
    if result.metadata.get("needs_confirmation"):
        assert True
    else:
        # playwright unavailable is also an acceptable hard failure
        assert "Playwright" in (result.error or "") or "confirm" in (result.error or "").lower()


def test_capabilities_report_includes_runtime_fields(monkeypatch):
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "1")
    clear_locality_cache()
    from app.tools.desktop.capabilities import audit_desktop_capabilities
    from app.tools.registry import get_default_tool_registry

    get_default_tool_registry.cache_clear()
    report = audit_desktop_capabilities()
    assert report.local_desktop is True
    by_id = {c.id: c for c in report.capabilities}
    assert "browser_automation" in by_id
    assert "local_files_allowlisted" in by_id
    assert by_id["os_ui_automation"].available is False
    assert by_id["unrestricted_shell"].available is False
    get_default_tool_registry.cache_clear()


def test_compound_detects_project_folder():
    from app.agent.compound import build_compound_plan

    plan = build_compound_plan(
        "Найди информацию о конкурентах, сделай презентацию и excel таблицу, "
        "сохрани всё в отдельной папке проекта"
    )
    kinds = [d.kind.value for d in plan.deliverables]
    assert "presentation" in kinds
    assert "spreadsheet" in kinds
    assert "project_folder" in kinds
