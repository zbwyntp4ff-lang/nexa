"""Playwright browser adapter — SSRF-gated, confirmation for significant actions."""
from __future__ import annotations

from typing import Any

from app.build.browser_verify import playwright_available
from app.plugins.base import PluginAdapter, PluginContext
from app.plugins.errors import PluginConfirmationRequiredError, PluginUnavailableError, PluginValidationError
from app.plugins.models import PluginActionSpec, PluginManifest, PluginResult, ProbeResult
from app.web.security import validate_url

_SUBMIT_HINTS = (
    "submit",
    "buy",
    "purchase",
    "checkout",
    "pay",
    "publish",
    "delete",
    "confirm",
    "send",
    "order",
)


class PlaywrightAdapter(PluginAdapter):
    manifest = PluginManifest(
        id="playwright",
        version="1.0.0",
        name="Playwright",
        description="Open pages, check elements, fill forms, and collect diagnostics. Does not replace Web Research. Significant actions (submit, publish, purchase) require confirmation.",
        category="browser",
        integration_type="browser",
        dependencies=["playwright Python package", "Chromium browser (playwright install chromium)"],
        required_permissions=["browser.navigate"],
        optional_permissions=["browser.interact", "browser.submit"],
        actions=[
            PluginActionSpec(
                name="open",
                description="Open a public http(s) page and return title + diagnostics",
                permissions=["browser.navigate"],
                input_schema={"url": {"type": "string"}},
            ),
            PluginActionSpec(
                name="query",
                description="Count matching elements",
                permissions=["browser.navigate"],
                input_schema={"url": {"type": "string"}, "selector": {"type": "string"}},
            ),
            PluginActionSpec(
                name="fill",
                description="Fill an input (no submit)",
                permissions=["browser.interact"],
                input_schema={"url": {"type": "string"}, "selector": {"type": "string"}, "value": {"type": "string"}},
            ),
            PluginActionSpec(
                name="click",
                description="Click an element; submit-like clicks need confirmation",
                permissions=["browser.interact"],
                dangerous=True,
                input_schema={"url": {"type": "string"}, "selector": {"type": "string"}},
            ),
        ],
        install_hint="pip install playwright && python -m playwright install chromium. For ordinary search use Research / web_research, not this plugin.",
    )

    async def probe(self, ctx: PluginContext) -> ProbeResult:
        if not playwright_available():
            return ProbeResult(
                ok=False,
                status="missing_dependency",
                detail="playwright package is not installed",
            )
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                path = pw.chromium.executable_path
                if not path:
                    return ProbeResult(
                        ok=False,
                        status="missing_dependency",
                        detail="Chromium executable is not installed (run playwright install chromium)",
                    )
                browser = await pw.chromium.launch(headless=True)
                await browser.close()
            return ProbeResult(
                ok=True,
                status="connected",
                detail="Playwright Chromium available",
                diagnostics={"chromium": path},
            )
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                ok=False,
                status="missing_dependency",
                detail=f"Playwright browsers unavailable: {exc}",
            )

    async def execute(self, action: str, params: dict[str, Any], ctx: PluginContext) -> PluginResult:
        url = str(params.get("url") or "").strip()
        if not url:
            raise PluginValidationError("url is required")
        selector = str(params.get("selector") or "")
        if action in {"query", "fill", "click"} and not selector:
            raise PluginValidationError("selector is required")
        if action == "click" and _looks_significant(selector) and not ctx.confirm:
            raise PluginConfirmationRequiredError("playwright", "click")
        if action == "fill" and params.get("submit") and not ctx.confirm:
            raise PluginConfirmationRequiredError("playwright", "fill")
        validate_url(url)
        if not playwright_available():
            raise PluginUnavailableError("playwright package is not installed")

        from playwright.async_api import async_playwright

        timeout_ms = int(min(ctx.timeout_seconds, 30) * 1000)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                page.set_default_timeout(timeout_ms)

                async def _ssrf_gate(route):  # type: ignore[no-untyped-def]
                    try:
                        validate_url(route.request.url)
                    except Exception:
                        await route.abort()
                        return
                    await route.continue_()

                await page.route("**/*", _ssrf_gate)
                response = await page.goto(url, wait_until="domcontentloaded")
                # Re-check final URL after any redirects Playwright followed.
                validate_url(page.url)
                console: list[str] = []
                page.on("console", lambda msg: console.append(f"{msg.type}: {msg.text}") if len(console) < 20 else None)
                title = await page.title()
                status = response.status if response else None
                extra: dict[str, Any] = {}
                if action == "query":
                    extra["count"] = await page.locator(selector).count()
                elif action == "fill":
                    if "browser.interact" not in ctx.granted_permissions:
                        raise PluginUnavailableError("browser.interact is not granted")
                    await page.fill(selector, str(params.get("value") or ""))
                    extra["filled"] = True
                    extra["submitted"] = False
                elif action == "click":
                    if _looks_significant(selector) and "browser.submit" not in ctx.granted_permissions:
                        raise PluginUnavailableError("browser.submit is not granted")
                    if "browser.interact" not in ctx.granted_permissions:
                        raise PluginUnavailableError("browser.interact is not granted")
                    await page.click(selector)
                    extra["clicked"] = True
                elif action != "open":
                    raise PluginValidationError(f"Unknown action '{action}'")
                return PluginResult(
                    success=True,
                    output={
                        "url": url,
                        "title": title,
                        "http_status": status,
                        "console": console,
                        **extra,
                    },
                )
            finally:
                await browser.close()


def _looks_significant(selector: str) -> bool:
    low = selector.lower()
    return any(h in low for h in _SUBMIT_HINTS)
