"""Runtime verification: HTTP preview + optional real Playwright browser."""
from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from app.build.browser_verify import (
    BrowserVerificationResult,
    browser_to_public,
    playwright_available,
    verify_preview_browser,
)
from app.core.logging_config import get_logger

logger = get_logger("nexa.build.runtime")

RuntimeMode = Literal["HTTP_PREVIEW", "BROWSER_PREVIEW", "NOT_AVAILABLE"]
BrowserInstrumentation = Literal["PLAYWRIGHT", "NOT_AVAILABLE"]
InteractionMode = Literal["BROWSER", "HTML_ASSET_PROBE", "NOT_AVAILABLE"]
RuntimeStatus = Literal["PASS", "FAIL", "PARTIAL", "NOT_AVAILABLE"]


class AssetCheck(BaseModel):
    path: str
    status: int | None = None
    ok: bool = False
    detail: str = ""


class RuntimeVerificationResult(BaseModel):
    """Honest runtime report — browser fields only set when Chromium actually ran."""

    runtime_verification: RuntimeMode = "NOT_AVAILABLE"
    browser_instrumentation: BrowserInstrumentation = "NOT_AVAILABLE"
    status: RuntimeStatus = "NOT_AVAILABLE"
    duration_ms: float = 0.0
    preview_url: str | None = None
    preview_http_status: int | None = None
    html_loaded: bool = False
    assets: list[AssetCheck] = Field(default_factory=list)
    elements_present: list[str] = Field(default_factory=list)
    interaction: InteractionMode = "NOT_AVAILABLE"
    # Browser-specific (empty unless browserAvailable)
    browser_available: bool = False
    page_loaded: bool = False
    console_errors: list[str] = Field(default_factory=list)
    runtime_errors: list[str] = Field(default_factory=list)
    failed_requests: list[str] = Field(default_factory=list)
    interactions: list[dict[str, Any]] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    passed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    browser: dict[str, Any] | None = None

    @property
    def preview_ok(self) -> bool:
        http_ok = (
            self.preview_http_status == 200
            and self.html_loaded
            and all(a.ok for a in self.assets if a.path)
        )
        if self.runtime_verification == "BROWSER_PREVIEW":
            return http_ok and self.page_loaded and self.status in {"PASS", "PARTIAL"}
        if self.runtime_verification == "HTTP_PREVIEW":
            return http_ok
        return False


def runtime_to_public(result: RuntimeVerificationResult) -> dict[str, Any]:
    return {
        "runtimeVerification": result.runtime_verification,
        "browserInstrumentation": result.browser_instrumentation,
        "status": result.status,
        "duration": result.duration_ms,
        "previewUrl": result.preview_url,
        "previewHttpStatus": result.preview_http_status,
        "htmlLoaded": result.html_loaded,
        "assets": [a.model_dump() for a in result.assets],
        "elementsPresent": list(result.elements_present),
        "interaction": result.interaction,
        "browserAvailable": result.browser_available,
        "pageLoaded": result.page_loaded,
        "consoleErrors": list(result.console_errors),
        "runtimeErrors": list(result.runtime_errors),
        "failedRequests": list(result.failed_requests),
        "interactions": list(result.interactions),
        "screenshots": list(result.screenshots),
        "passed": list(result.passed),
        "failed": list(result.failed),
        "warnings": list(result.warnings),
        "browser": result.browser,
    }


def not_available_runtime(*, reason: str = "no HTTP preview client") -> RuntimeVerificationResult:
    return RuntimeVerificationResult(
        runtime_verification="NOT_AVAILABLE",
        browser_instrumentation="NOT_AVAILABLE",
        status="NOT_AVAILABLE",
        interaction="NOT_AVAILABLE",
        warnings=[
            f"runtimeVerification: NOT_AVAILABLE ({reason})",
            "browserInstrumentation: NOT_AVAILABLE",
        ],
    )


async def verify_preview_http(
    *,
    project_id: str,
    entry_file: str = "index.html",
    preview_path: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> RuntimeVerificationResult:
    """Verify live preview over HTTP (ASGI). Does not launch a browser."""
    path = preview_path or f"/api/v1/build/preview/{project_id}/{entry_file}"
    result = RuntimeVerificationResult(
        runtime_verification="HTTP_PREVIEW",
        browser_instrumentation="NOT_AVAILABLE",
        preview_url=path,
        interaction="HTML_ASSET_PROBE",
        status="PARTIAL",
        warnings=["browserInstrumentation: NOT_AVAILABLE (HTTP-only pass)"],
    )

    from app.build.engine import resolve_preview_file

    if resolve_preview_file(project_id, entry_file) is None:
        result.failed.append("Preview file not resolvable in workspace")
        result.status = "FAIL"
        return result

    owns_client = client is None
    if client is None:
        try:
            from app.main import app as fastapi_app

            transport = httpx.ASGITransport(app=fastapi_app)
            client = httpx.AsyncClient(transport=transport, base_url="http://nexa-preview")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ASGI preview client unavailable: %s", exc)
            return not_available_runtime(reason=f"ASGI client failed: {exc}")

    try:
        response = await client.get(path)
        result.preview_http_status = response.status_code
        if response.status_code != 200:
            result.failed.append(f"Preview HTTP {response.status_code}")
            result.status = "FAIL"
            return result
        result.passed.append("Preview HTTP 200")
        html = response.text
        if "<html" not in html.lower():
            result.failed.append("Preview HTML not loaded")
            result.status = "FAIL"
            return result
        result.html_loaded = True
        result.passed.append("Preview HTML loaded")

        checks = {
            "canvas": bool(re.search(r"<canvas\b", html, re.I)),
            "script": bool(re.search(r"<script\b", html, re.I)),
            "stylesheet": bool(re.search(r'rel=["\']stylesheet["\']', html, re.I)),
            "score_hud": 'id="score"' in html or "score" in html.lower(),
        }
        for name, present in checks.items():
            if present:
                result.elements_present.append(name)
                result.passed.append(f"Element present: {name}")
            elif name in {"canvas", "script"}:
                result.failed.append(f"Element missing in loaded HTML: {name}")

        refs = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html, flags=re.I)
        base_dir = path.rsplit("/", 1)[0] + "/"
        for ref in refs:
            if ref.startswith(("http://", "https://", "#", "data:", "//")):
                continue
            if ".." in ref.replace("\\", "/").split("/"):
                result.assets.append(AssetCheck(path=ref, ok=False, detail="path traversal blocked"))
                result.failed.append(f"Unsafe asset ref: {ref}")
                continue
            asset_url = urljoin(base_dir, ref)
            try:
                asset_resp = await client.get(asset_url)
                ok = asset_resp.status_code == 200 and len(asset_resp.content) > 0
                result.assets.append(
                    AssetCheck(
                        path=ref,
                        status=asset_resp.status_code,
                        ok=ok,
                        detail="ok" if ok else f"HTTP {asset_resp.status_code}",
                    )
                )
                if ok:
                    result.passed.append(f"Asset loaded: {ref}")
                else:
                    result.failed.append(f"Asset failed: {ref} HTTP {asset_resp.status_code}")
            except httpx.HTTPError:
                result.assets.append(AssetCheck(path=ref, ok=False, detail="error"))
                result.failed.append(f"Asset error: {ref}")

        js_assets = [a for a in result.assets if a.path.endswith(".js") and a.ok]
        if js_assets:
            js_url = urljoin(base_dir, js_assets[0].path)
            try:
                js_resp = await client.get(js_url)
                if "requestAnimationFrame" in js_resp.text:
                    result.passed.append("Game loop present in loaded JS")
                    result.elements_present.append("game_loop")
            except httpx.HTTPError:
                result.warnings.append("Could not re-fetch JS for loop probe")

        result.passed.append("interaction: HTML_ASSET_PROBE (HTTP stage)")
        result.status = "PASS" if not result.failed else "FAIL"
    finally:
        if owns_client and client is not None:
            await client.aclose()

    return result


def _merge_browser(
    http: RuntimeVerificationResult, browser: BrowserVerificationResult
) -> RuntimeVerificationResult:
    merged = http.model_copy(deep=True)
    merged.browser = browser_to_public(browser)
    merged.browser_available = browser.browser_available
    merged.page_loaded = browser.page_loaded
    merged.console_errors = list(browser.console_errors)
    merged.runtime_errors = list(browser.runtime_errors)
    merged.failed_requests = list(browser.failed_requests)
    merged.interactions = [i.model_dump() for i in browser.interactions]
    merged.screenshots = list(browser.screenshots)
    merged.duration_ms = browser.duration_ms

    if not browser.browser_available and browser.status == "SKIPPED":
        merged.browser_instrumentation = "NOT_AVAILABLE"
        merged.warnings.append(f"browserInstrumentation: NOT_AVAILABLE ({browser.detail})")
        merged.warnings.append("browser verification skipped — HTTP_PREVIEW only")
        return merged

    merged.browser_instrumentation = "PLAYWRIGHT"
    merged.runtime_verification = "BROWSER_PREVIEW"
    merged.interaction = "BROWSER"
    # Drop HTTP-only "NOT_AVAILABLE" browser warnings
    merged.warnings = [w for w in merged.warnings if "browserInstrumentation: NOT_AVAILABLE" not in w]

    if browser.page_loaded:
        merged.passed.append("Browser page loaded")
        merged.elements_present = list(
            dict.fromkeys(merged.elements_present + browser.elements_found)
        )
    else:
        merged.failed.append("Browser page not loaded")

    for err in browser.console_errors:
        merged.failed.append(f"Console error: {err}")
    for err in browser.runtime_errors:
        merged.failed.append(f"Runtime error: {err}")
    for err in browser.failed_requests:
        merged.failed.append(f"Network error: {err}")

    for inter in browser.interactions:
        if inter.ok:
            merged.passed.append(f"Interaction OK: {inter.name}")
        else:
            merged.failed.append(f"Interaction failed: {inter.name}")

    if browser.screenshots:
        merged.passed.append(f"Screenshot captured ({len(browser.screenshots)})")

    if browser.status == "PASS" and http.status != "FAIL":
        merged.status = "PASS"
    elif browser.status == "FAIL" or http.status == "FAIL":
        merged.status = "FAIL"
    else:
        merged.status = "PARTIAL"

    return merged


async def verify_preview_runtime(
    *,
    project_id: str,
    entry_file: str = "index.html",
    preview_path: str | None = None,
    enable_browser: bool = True,
) -> RuntimeVerificationResult:
    """HTTP preview verification, then real Playwright browser if available."""
    http = await verify_preview_http(
        project_id=project_id,
        entry_file=entry_file,
        preview_path=preview_path,
    )
    if not enable_browser:
        return http

    if not playwright_available():
        http.warnings.append("browserInstrumentation: NOT_AVAILABLE (playwright not installed)")
        return http

    browser = await verify_preview_browser(
        project_id=project_id,
        entry_file=entry_file,
        do_interactions=True,
        screenshot=True,
    )
    return _merge_browser(http, browser)
