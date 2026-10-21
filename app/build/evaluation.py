"""Evaluation Engine V1 — score project against user intent (no CoT)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.build.plan import BuildPlan
from app.build.understanding import RequestUnderstanding

EvalStatus = Literal["PASS", "NEEDS_IMPROVEMENT", "FAIL"]

DEFAULT_PASS_THRESHOLD = 70
MAX_IMPROVEMENT_ATTEMPTS = 3


class EvaluationResult(BaseModel):
    score: int = Field(ge=0, le=100)
    status: EvalStatus
    requirements: list[str] = Field(default_factory=list)
    passed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    criteria: dict[str, int] = Field(default_factory=dict)
    runtime: dict | None = None


_ENEMY_REQ = re.compile(r"враг|enemy|enemies", re.I)
_CAR_REQ = re.compile(r"машин|car|vehicle", re.I)
_COIN_REQ = re.compile(r"монет|coin|collect|собира", re.I)
_GAME_OVER_REQ = re.compile(r"game\s*over|гейм\s*овер", re.I)
_SCORE_REQ = re.compile(r"очк|score", re.I)
_THREE_REQ = re.compile(r"3\s*d|three\.?js|webgl|трёхмер|трехмер|гонк|racing|пол[её]т|flight|танк|tank|приключ|adventure", re.I)


def evaluate_project(
    *,
    user_request: str,
    plan: BuildPlan,
    files: dict[str, str],
    preview_ok: bool,
    tests_passed: bool,
    pass_threshold: int = DEFAULT_PASS_THRESHOLD,
    runtime_result: Any | None = None,
) -> EvaluationResult:
    """Deterministic checks with short verifiable reasons only.

    ``runtime_result`` — optional :class:`RuntimeVerificationResult` from HTTP
    preview probes. Browser console/network is never faked.
    """
    from app.build.runtime_verify import RuntimeVerificationResult, runtime_to_public

    understanding = plan.understanding or RequestUnderstanding(goal=user_request)
    reqs = _collect_requirements(user_request, understanding, plan)
    html = files.get("index.html", "") or files.get(plan.entry_file, "")
    js = files.get("main.js", "")
    css = files.get("style.css", "")
    all_text = "\n".join(files.values())

    passed: list[str] = []
    failed: list[str] = []
    warnings: list[str] = []
    suggested: list[str] = []
    scores: dict[str, list[bool]] = {
        "functionality": [],
        "requirements": [],
        "ui_ux": [],
        "runtime": [],
        "build_quality": [],
        "user_intent": [],
    }

    def ok(bucket: str, reason: str) -> None:
        passed.append(reason)
        scores[bucket].append(True)

    def bad(bucket: str, reason: str, fix: str | None = None) -> None:
        failed.append(reason)
        scores[bucket].append(False)
        if fix:
            suggested.append(fix)

    def warn(reason: str) -> None:
        warnings.append(reason)

    runtime: RuntimeVerificationResult | None = None
    if isinstance(runtime_result, RuntimeVerificationResult):
        runtime = runtime_result
    elif runtime_result is None:
        runtime = None

    # --- RUNTIME / BUILD ---
    if tests_passed:
        ok("runtime", "Tests PASS")
        ok("build_quality", "Build/tests успешны")
    else:
        bad("runtime", "Tests FAIL", "repair_tests")
        bad("build_quality", "Build/tests не успешны", "repair_tests")

    if runtime is not None and runtime.runtime_verification in {"HTTP_PREVIEW", "BROWSER_PREVIEW"}:
        warnings.extend(runtime.warnings)
        if runtime.preview_http_status == 200 and runtime.html_loaded:
            ok("runtime", "Preview отвечает HTTP 200")
            ok("runtime", "Preview HTML loaded")
            ok("build_quality", "Preview файл доступен")
        else:
            bad("runtime", "Preview HTTP/HTML verification failed", "fix_preview")
            bad("build_quality", "Preview недоступен", "fix_preview")
        for reason in runtime.passed:
            if reason.startswith("Asset loaded"):
                ok("runtime", reason)
            elif reason.startswith("Element present") or reason.startswith("Browser page"):
                ok("ui_ux", reason)
            elif reason.startswith("Game loop"):
                ok("functionality", reason)
                ok("user_intent", reason)
            elif reason.startswith("Interaction OK"):
                ok("functionality", reason)
                ok("ui_ux", reason)
            elif reason.startswith("Screenshot"):
                ok("ui_ux", reason)
        for reason in runtime.failed:
            if reason.startswith("Asset"):
                bad("runtime", reason, "restore_asset")
            elif "Element missing" in reason:
                bad("ui_ux", reason)
            elif reason.startswith("Console error") or reason.startswith("Runtime error"):
                bad("runtime", reason, "fix_js_runtime_error")
            elif reason.startswith("Network error"):
                bad("runtime", reason, "fix_network_asset")
            elif reason.startswith("Interaction failed"):
                bad("functionality", reason)
                bad("ui_ux", reason)
            else:
                bad("runtime", reason, "fix_preview")
        if runtime.runtime_verification == "BROWSER_PREVIEW":
            if runtime.browser_available and runtime.page_loaded:
                ok("runtime", "Browser verification ran")
            if runtime.interaction == "BROWSER":
                ok("ui_ux", "interaction: BROWSER")
            if runtime.browser_instrumentation == "PLAYWRIGHT":
                ok("runtime", "browserInstrumentation: PLAYWRIGHT")
        elif runtime.interaction == "HTML_ASSET_PROBE":
            ok("ui_ux", "interaction: HTML_ASSET_PROBE")
            warn("browserInstrumentation: NOT_AVAILABLE")
    elif runtime is not None and runtime.runtime_verification == "NOT_AVAILABLE":
        warnings.extend(runtime.warnings or ["runtimeVerification: NOT_AVAILABLE"])
        warn("runtimeVerification: NOT_AVAILABLE")
        warn("browserInstrumentation: NOT_AVAILABLE")
        # Fall back to disk/structural preview flag — do NOT claim HTTP 200
        if preview_ok:
            ok("build_quality", "Preview файл доступен (disk)")
            warn("Preview HTTP not verified (runtimeVerification NOT_AVAILABLE)")
        else:
            bad("build_quality", "Preview файл отсутствует", "fix_preview")
    else:
        warn("runtimeVerification: NOT_AVAILABLE")
        warn("browserInstrumentation: NOT_AVAILABLE")
        if preview_ok:
            ok("build_quality", "Preview файл доступен (disk)")
            warn("Preview HTTP not verified (no runtime probe)")
        else:
            bad("build_quality", "Preview файл отсутствует", "fix_preview")

    # Broken asset refs (static structure — kept even when HTTP probe ran)
    for ref in re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html, flags=re.I):
        if ref.startswith(("http://", "https://", "#", "data:")):
            continue
        name = ref.split("?")[0].lstrip("./")
        if name and name not in files and not any(k.endswith(name) for k in files):
            bad("runtime", f"Broken asset: {name}", "restore_asset")

    # Structure
    if plan.entry_file in files or "index.html" in files:
        ok("build_quality", "Структура: entry HTML есть")
    else:
        bad("build_quality", "Нет entry HTML", "restore_entry")

    if plan.type == "web_game" and "main.js" not in files:
        bad("build_quality", "Нет main.js для игры", "restore_main_js")

    extras = [
        n
        for n in files
        if n not in {"index.html", "style.css", "main.js", "README.md", "scene.json", plan.entry_file}
    ]
    if len(extras) > 8:
        warn(f"Много дополнительных файлов: {len(extras)}")

    is_three = (
        "THREE" in js
        or "WebGLRenderer" in js
        or "three.min.js" in html
        or "scene.json" in files
        or bool(_THREE_REQ.search(user_request))
    )

    # --- UI/UX ---
    if plan.type in {"web_game", "static_site", "frontend_app", "tool"} or html:
        if "<canvas" in html.lower() or plan.type != "web_game":
            if plan.type == "web_game":
                if "<canvas" in html.lower():
                    ok("ui_ux", "Canvas элемент присутствует")
                else:
                    bad("ui_ux", "Canvas отсутствует", "add_canvas")
            else:
                ok("ui_ux", "HTML разметка присутствует")
        if "viewport" in html.lower():
            ok("ui_ux", "Viewport meta присутствует")
        else:
            bad("ui_ux", "Viewport meta отсутствует", "add_viewport")
        if "@media" in css or "nexa-v2-improve" in css:
            ok("ui_ux", "Responsive стили присутствуют")
        else:
            warn("Responsive стили не найдены")
            suggested.append("add_responsive")
        if 'id="score"' in html or "score" in js.lower():
            ok("ui_ux", "HUD/score элемент usable")
        elif plan.type == "web_game":
            bad("ui_ux", "HUD/score отсутствует", "add_score_hud")

    # --- FUNCTIONALITY / INTENT / REQUIREMENTS ---
    need_car = bool(_CAR_REQ.search(user_request)) or any("машин" in r.lower() for r in reqs)
    need_coins = bool(_COIN_REQ.search(user_request)) or any("монет" in r.lower() for r in reqs)
    need_enemies = bool(_ENEMY_REQ.search(user_request)) or any("враг" in r.lower() for r in reqs)
    need_game_over = bool(_GAME_OVER_REQ.search(user_request))
    need_score = bool(_SCORE_REQ.search(user_request)) or any("очк" in r.lower() for r in reqs)
    need_three = is_three or any("three" in r.lower() or "webgl" in r.lower() or "3d" in r.lower() for r in reqs)

    if plan.type == "web_game" or need_car or need_coins or need_three:
        if "requestAnimationFrame" in js:
            ok("functionality", "Игровой цикл реализован")
            ok("user_intent", "Игра запускается (game loop)")
        else:
            bad("functionality", "Игровой цикл отсутствует", "add_game_loop")
            bad("user_intent", "Игра не запускается", "add_game_loop")

    if need_three:
        if "WebGLRenderer" in js or "THREE.WebGLRenderer" in js:
            ok("functionality", "Three.js WebGLRenderer присутствует")
            ok("requirements", "3D рендер")
            ok("user_intent", "Three.js соответствует запросу")
        else:
            bad("functionality", "Three.js WebGLRenderer отсутствует", "add_three_renderer")
            bad("requirements", "Нет 3D рендера", "add_three_renderer")
        if "keydown" in js or "keys" in js:
            ok("functionality", "3D управление реализовано")
        else:
            bad("functionality", "3D управление отсутствует", "add_controls")
        if "endGame" in js or "overlay" in js or "finish" in js.lower() or "won" in js:
            ok("functionality", "Условие победы/поражения есть")
        if "scene.json" in files:
            ok("build_quality", "scene.json присутствует")

    if need_car:
        # Check implementation code — not README marketing text
        if (
            re.search(r"\bcar\b", js, re.I)
            or "makeCar" in js
            or "player" in js
            or "машин" in js.lower()
        ):
            ok("functionality", "Машина реализована")
            ok("requirements", "Машина как игрок")
            ok("user_intent", "Машина соответствует запросу")
        else:
            bad("functionality", "Машина отсутствует", "add_car")
            bad("requirements", "Нет машины", "add_car")
            bad("user_intent", "Нет машины в результате", "add_car")

    if need_coins:
        if "coins" in js or "монет" in js.lower() or "coin" in js.lower():
            ok("functionality", "Монеты реализованы")
            ok("requirements", "Монеты на поле")
            ok("user_intent", "Монеты соответствуют запросу")
        else:
            bad("functionality", "Монеты отсутствуют", "add_coins")
            bad("requirements", "Нет монет", "add_coins")
            bad("user_intent", "Нет монет в результате", "add_coins")

    if need_enemies:
        enemies_on = bool(
            re.search(r"__NEXA_ENEMIES__\s*=\s*[1-9]", js)
            or re.search(r"spawnEnemies\(\s*[1-9]", js)
            or re.search(r"enemies\s*=\s*\[[^\]]+\w", js)
        )
        if enemies_on or ("enemies" in js and "__NEXA_ENEMIES__ || 0" not in js and "|| 0" not in js):
            # also accept if spawnEnemies called with positive default
            ok("functionality", "Враги реализованы")
            ok("requirements", "Враги в игре")
            ok("user_intent", "Враги соответствуют запросу")
        elif "enemies" in js and (
            "__NEXA_ENEMIES__ || 0" in js or "spawnEnemies(window.__NEXA_ENEMIES__ || 0)" in js
        ):
            # code present but disabled
            bad("functionality", "Враги выключены (count=0)", "enable_enemies")
            bad("requirements", "Враги не активны", "enable_enemies")
            bad("user_intent", "Враги не соответствуют запросу", "enable_enemies")
        else:
            bad("functionality", "Враги отсутствуют", "enable_enemies")
            bad("requirements", "Нет врагов", "enable_enemies")
            bad("user_intent", "Нет врагов в результате", "enable_enemies")

    if need_game_over:
        if "nexa-game-over" in js or 'id="game-over"' in html:
            ok("functionality", "Game Over реализован")
        else:
            bad("functionality", "Game Over отсутствует", "add_game_over")

    if need_score:
        if "nexa-score-system" in js or 'id="score"' in html:
            ok("functionality", "Система очков реализована")
        else:
            bad("functionality", "Система очков отсутствует", "add_score")

    # Restart usable
    if plan.type == "web_game":
        if re.search(r'keys\.has\(["\']r["\']\)|"r"\)|Restart|рестарт', js + html, re.I):
            ok("ui_ux", "Restart доступен")
        else:
            bad("ui_ux", "Кнопка Restart отсутствует", "add_restart")

    # Must-have coverage
    for req in understanding.must_have:
        rl = req.lower()
        if "цикл" in rl and "requestAnimationFrame" in js:
            ok("requirements", f"Must-have: {req}")
        elif "машин" in rl and ("car" in js or "машин" in js.lower()):
            ok("requirements", f"Must-have: {req}")
        elif "монет" in rl and ("coins" in js or "coin" in js.lower()):
            ok("requirements", f"Must-have: {req}")
        elif "монет" in rl:
            bad("requirements", f"Must-have не выполнен: {req}", "add_coins")
        elif "управлен" in rl and ("keydown" in js or "keys" in js):
            ok("requirements", f"Must-have: {req}")
        elif "очк" in rl or "прогресс" in rl:
            if "score" in js.lower() or 'id="score"' in html:
                ok("requirements", f"Must-have: {req}")
            else:
                bad("requirements", f"Must-have не выполнен: {req}", "add_score")
        elif "preview" in rl and preview_ok:
            ok("requirements", f"Must-have: {req}")
        elif "index.html" in rl and html:
            ok("requirements", f"Must-have: {req}")
        # else: skip soft must-haves already covered elsewhere

    criteria_scores: dict[str, int] = {}
    for name, flags in scores.items():
        if not flags:
            criteria_scores[name] = 100
        else:
            criteria_scores[name] = int(round(100 * sum(1 for f in flags if f) / len(flags)))

    # Weighted total
    weights = {
        "functionality": 0.25,
        "requirements": 0.20,
        "ui_ux": 0.15,
        "runtime": 0.15,
        "build_quality": 0.10,
        "user_intent": 0.15,
    }
    total = int(round(sum(criteria_scores[k] * w for k, w in weights.items())))
    total = max(0, min(100, total))

    has_critical = any(
        f.startswith(
            (
                "Машина отсутствует",
                "Монеты отсутствуют",
                "Враги",
                "Игровой цикл",
                "Preview недоступен",
                "Preview HTTP",
                "Console error",
                "Runtime error",
                "Network error",
                "Tests FAIL",
            )
        )
        for f in failed
    )
    if total >= pass_threshold and not has_critical:
        status: EvalStatus = "PASS"
    elif total >= max(40, pass_threshold - 25) or suggested:
        status = "NEEDS_IMPROVEMENT"
    else:
        status = "FAIL"

    uniq_fixes: list[str] = []
    for fix in suggested:
        if fix not in uniq_fixes:
            uniq_fixes.append(fix)

    runtime_public = None
    if runtime is not None:
        runtime_public = runtime_to_public(runtime)

    return EvaluationResult(
        score=total,
        status=status,
        requirements=reqs,
        passed=_uniq(passed),
        failed=_uniq(failed),
        warnings=_uniq(warnings),
        suggested_fixes=uniq_fixes,
        criteria=criteria_scores,
        runtime=runtime_public,
    )


def evaluation_to_public(result: EvaluationResult) -> dict:
    """API-facing dump — short reasons only, camelCase suggestedFixes."""
    return {
        "score": result.score,
        "status": result.status,
        "requirements": list(result.requirements),
        "passed": list(result.passed),
        "failed": list(result.failed),
        "warnings": list(result.warnings),
        "suggestedFixes": list(result.suggested_fixes),
        "criteria": dict(result.criteria),
        "runtime": result.runtime,
    }


def _collect_requirements(
    user_request: str,
    understanding: RequestUnderstanding,
    plan: BuildPlan,
) -> list[str]:
    reqs = list(understanding.must_have) + list(plan.requirements)
    if _CAR_REQ.search(user_request):
        reqs.append("машина")
    if _COIN_REQ.search(user_request):
        reqs.append("монеты")
    if _ENEMY_REQ.search(user_request):
        reqs.append("враги")
    return _uniq(reqs)


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def load_project_files(root: Path, names: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in names:
        path = root / name
        if path.is_file():
            try:
                files[name] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    return files
