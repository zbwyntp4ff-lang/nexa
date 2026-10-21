"""Audit which computer-control capabilities are actually available right now."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.tools.desktop.locality import is_local_desktop


class CapabilityItem(BaseModel):
    id: str
    available: bool
    tool_name: str | None = None
    notes: str = ""
    requires_local_desktop: bool = False
    requires_confirm: bool = False


class DesktopCapabilityReport(BaseModel):
    """Machine-readable capability matrix — never claim OS control without a tool."""

    local_desktop: bool = False
    capabilities: list[CapabilityItem] = Field(default_factory=list)
    summary: str = ""


def audit_desktop_capabilities() -> DesktopCapabilityReport:
    """Inspect registry + runtime probes (Playwright, locality)."""
    from app.build.browser_verify import playwright_available
    from app.tools.registry import get_default_tool_registry

    registry = get_default_tool_registry()
    names = {t.name for t in registry.list()}
    local = is_local_desktop()
    pw = False
    pw_detail = "not checked"
    try:
        pw = bool(playwright_available())
        pw_detail = "Playwright package importable" if pw else "playwright package missing"
        if pw:
            # Soft probe — do not fail the whole audit if chromium binary missing.
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    exe = getattr(p.chromium, "executable_path", None)
                    if not exe:
                        pw = False
                        pw_detail = "Playwright installed but Chromium executable missing"
                    else:
                        pw_detail = f"Chromium available ({exe})"
            except Exception as exc:  # noqa: BLE001
                pw = False
                pw_detail = f"Chromium probe failed: {exc.__class__.__name__}"
    except Exception as exc:  # noqa: BLE001
        pw_detail = f"probe error: {exc.__class__.__name__}"

    browser_ok = "browser" in names and pw
    local_files_ok = "local_files" in names and local
    open_ok = "open_result" in names and local

    items = [
        CapabilityItem(
            id="sandbox_file_read",
            available="file_read" in names,
            tool_name="file_read",
            notes="Read files only inside agent_workspace sandbox.",
        ),
        CapabilityItem(
            id="sandbox_file_write",
            available="file_write" in names or "file_create" in names,
            tool_name="file_write",
            notes="Write/create inside sandbox; refuses overwrite via file_create.",
        ),
        CapabilityItem(
            id="sandbox_directory",
            available="directory_list" in names,
            tool_name="directory_list",
            notes="List/create directories inside sandbox only.",
        ),
        CapabilityItem(
            id="office_generate",
            available="create_presentation" in names,
            tool_name="create_presentation",
            notes="PPTX/DOCX/XLSX/PDF generation + /api/v1/results download.",
        ),
        CapabilityItem(
            id="web_research",
            available="web_research" in names,
            tool_name="web_research",
            notes="DuckDuckGo Lite search + page fetch (SSRF-filtered).",
        ),
        CapabilityItem(
            id="browser_automation",
            available=browser_ok,
            tool_name="browser",
            notes=pw_detail
            + ". Significant clicks/submits require confirm=true. SSRF-gated.",
            requires_confirm=True,
        ),
        CapabilityItem(
            id="local_files_allowlisted",
            available=local_files_ok,
            tool_name="local_files",
            notes=(
                "Allowlisted dirs (agent_workspace + NEXA_DESKTOP_ALLOWED_DIRS). "
                if local
                else "Disabled: backend is not local desktop (NEXA_LOCAL_DESKTOP)."
            ),
            requires_local_desktop=True,
            requires_confirm=True,
        ),
        CapabilityItem(
            id="open_result_default_app",
            available=open_ok,
            tool_name="open_result",
            notes=(
                "Opens allowlisted/result files via OS default handler; confirm required. "
                "Does not claim PowerPoint is installed unless probed."
                if local
                else "Disabled on remote backends."
            ),
            requires_local_desktop=True,
            requires_confirm=True,
        ),
        CapabilityItem(
            id="open_os_applications",
            available=False,
            tool_name=None,
            notes="No generic launch of arbitrary installed apps — only open_result for allowlisted files.",
        ),
        CapabilityItem(
            id="os_ui_automation",
            available=False,
            tool_name=None,
            notes="Not implemented — no mouse/keyboard OS control.",
        ),
        CapabilityItem(
            id="unrestricted_shell",
            available=False,
            tool_name=None,
            notes="Not implemented — no unrestricted shell.",
        ),
        CapabilityItem(
            id="electron_ipc_bridge",
            available=True,  # Code present in desktop shell; runtime only in Electron.
            tool_name=None,
            notes=(
                "Electron preload exposes fixed IPC (getAppInfo, openExternal, openPath). "
                "Available only inside the desktop shell, not in a plain browser tab."
            ),
            requires_local_desktop=True,
            requires_confirm=True,
        ),
        CapabilityItem(
            id="plugin_extensions",
            available=any(n.startswith("plugin_") for n in names),
            tool_name="plugin_*",
            notes="Optional Plugin Hub adapters when connected by the user.",
        ),
    ]
    available = sum(1 for i in items if i.available)
    summary = (
        f"local_desktop={local}; {available}/{len(items)} capabilities available. "
        "Remote backends refuse OS file open / local_files. "
        "NEXA does not claim full computer control."
    )
    return DesktopCapabilityReport(
        local_desktop=local,
        capabilities=items,
        summary=summary,
    )
