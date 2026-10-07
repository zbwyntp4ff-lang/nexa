"""Real Chromium browser verification via Playwright (no fakes)."""
from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.build import store
from app.core.logging_config import get_logger

logger = get_logger("nexa.build.browser")

BrowserStatus = Literal["PASS", "FAIL", "SKIPPED"]


class InteractionResult(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class BrowserVerificationResult(BaseModel):
    browser_available: bool = False
    page_loaded: bool = False
    console_errors: list[str] = Field(default_factory=list)
    runtime_errors: list[str] = Field(default_factory=list)
    failed_requests: list[str] = Field(default_factory=list)
    interactions: list[InteractionResult] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    status: BrowserStatus = "SKIPPED"
    duration_ms: float = 0.0
    detail: str = ""
    elements_found: list[str] = Field(default_factory=list)


def browser_to_public(result: BrowserVerificationResult) -> dict[str, Any]:
    return {
        "browserAvailable": result.browser_available,
        "pageLoaded": result.page_loaded,
        "consoleErrors": list(result.console_errors),
        "runtimeErrors": list(result.runtime_errors),
        "failedRequests": list(result.failed_requests),
        "interactions": [i.model_dump() for i in result.interactions],
        "screenshots": list(result.screenshots),
        "status": result.status,
        "duration": result.duration_ms,
        "detail": result.detail,
        "elementsFound": list(result.elements_found),
    }


def playwright_available() -> bool:
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        return False
    return True


async def verify_preview_browser(
    *,
    project_id: str,
    entry_file: str = "index.html",
    do_interactions: bool = True,
    screenshot: bool = True,
) -> BrowserVerificationResult:
    """
    Launch real Chromium, open project files via route fulfill, capture
    console / pageerrors / failed requests, optionally interact and screenshot.
    """
    started = time.perf_counter()
    result = BrowserVerificationResult()

    if not playwright_available():
        result.status = "SKIPPED"
        result.detail = "playwright package not installed"
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    from app.build.engine import resolve_preview_file

    entry = resolve_preview_file(project_id, entry_file)
    if entry is None:
        result.browser_available = True  # package exists but project missing
        result.status = "FAIL"
        result.detail = "preview entry not found"
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    record = store.get_project(project_id)
    if record is None:
        result.status = "FAIL"
        result.detail = "project record missing"
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    root = (store.workspace_root() / record.root_rel).resolve()
    origin = "http://nexa-preview.local"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        result.status = "SKIPPED"
        result.detail = "playwright import failed"
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as exc:  # noqa: BLE001
                result.status = "SKIPPED"
                result.detail = f"chromium launch failed: {exc}"
                result.duration_ms = (time.perf_counter() - started) * 1000
                logger.warning("playwright chromium launch failed: %s", exc)
                return result

            result.browser_available = True
            context = await browser.new_context()
            page = await context.new_page()

            def on_console(msg) -> None:
                if msg.type == "error":
                    text = msg.text
                    result.console_errors.append(text)

            def on_page_error(exc) -> None:
                result.runtime_errors.append(str(exc))

            def on_request_failed(req) -> None:
                result.failed_requests.append(f"{req.method} {req.url} :: {req.failure}")

            def on_response(resp) -> None:
                if resp.status >= 400:
                    result.failed_requests.append(f"HTTP {resp.status} {resp.url}")

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)
            page.on("response", on_response)

            async def fulfill_route(route) -> None:
                url = route.request.url
                parsed = urlparse(url)
                rel = parsed.path.lstrip("/") or entry_file
                if rel in ("", "/"):
                    rel = entry_file
                # Only serve files under project root
                candidate = (root / rel).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    await route.abort()
                    return
                if not candidate.is_file():
                    await route.abort()
                    return
                mime, _ = mimetypes.guess_type(str(candidate))
                body = candidate.read_bytes()
                await route.fulfill(status=200, body=body, content_type=mime or "application/octet-stream")

            await page.route(f"{origin}/**", fulfill_route)
            await page.route("**/nexa-preview.local/**", fulfill_route)

            target = f"{origin}/{entry_file}"
            try:
                response = await page.goto(target, wait_until="load", timeout=15000)
            except Exception as exc:  # noqa: BLE001
                result.status = "FAIL"
                result.detail = f"page.goto failed: {exc}"
                await browser.close()
                result.duration_ms = (time.perf_counter() - started) * 1000
                return result

            if response is None or response.status >= 400:
                result.status = "FAIL"
                result.detail = f"navigation status={getattr(response, 'status', None)}"
            else:
                result.page_loaded = True

            # Allow scripts to run briefly
            await page.wait_for_timeout(400)

            # Detect elements
            for sel, name in (
                ("canvas", "canvas"),
                ("#score", "score_hud"),
                ("#game", "game"),
                ("script", "script"),
            ):
                try:
                    if await page.locator(sel).count() > 0:
                        result.elements_found.append(name)
                except Exception:  # noqa: BLE001
                    pass

            if do_interactions and result.page_loaded:
                # Focus canvas / body and send real key events
                try:
                    canvas = page.locator("canvas").first
                    if await canvas.count() > 0:
                        await canvas.click(timeout=3000)
                        result.interactions.append(
                            InteractionResult(name="click_canvas", ok=True, detail="clicked")
                        )
                    else:
                        await page.click("body", timeout=3000)
                        result.interactions.append(
                            InteractionResult(name="click_body", ok=True, detail="no canvas")
                        )
                except Exception as exc:  # noqa: BLE001
                    result.interactions.append(
                        InteractionResult(name="click", ok=False, detail=str(exc))
                    )

                try:
                    await page.keyboard.press("ArrowUp")
                    await page.keyboard.press("ArrowRight")
                    result.interactions.append(
                        InteractionResult(name="keyboard_arrows", ok=True, detail="ArrowUp+ArrowRight")
                    )
                except Exception as exc:  # noqa: BLE001
                    result.interactions.append(
                        InteractionResult(name="keyboard_arrows", ok=False, detail=str(exc))
                    )

                await page.wait_for_timeout(200)

            if screenshot and result.page_loaded:
                shot_dir = root / ".nexa_runtime"
                shot_dir.mkdir(parents=True, exist_ok=True)
                shot_path = shot_dir / "browser_verify.png"
                try:
                    await page.screenshot(path=str(shot_path), full_page=True)
                    result.screenshots.append(str(shot_path))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("screenshot failed: %s", exc)

            await browser.close()
    except Exception as exc:  # noqa: BLE001
        result.status = "FAIL"
        result.detail = f"browser session error: {exc}"
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    result.duration_ms = (time.perf_counter() - started) * 1000
    has_errors = bool(result.console_errors or result.runtime_errors or result.failed_requests)
    interaction_ok = all(i.ok for i in result.interactions) if result.interactions else True
    if result.page_loaded and not has_errors and interaction_ok:
        result.status = "PASS"
        result.detail = "browser verification passed"
    else:
        result.status = "FAIL"
        parts = []
        if not result.page_loaded:
            parts.append("page not loaded")
        if result.console_errors:
            parts.append(f"console={len(result.console_errors)}")
        if result.runtime_errors:
            parts.append(f"runtime={len(result.runtime_errors)}")
        if result.failed_requests:
            parts.append(f"network={len(result.failed_requests)}")
        if not interaction_ok:
            parts.append("interaction failed")
        result.detail = "; ".join(parts) or "browser verification failed"

    return result
