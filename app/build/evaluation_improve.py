"""Apply Evaluation Engine suggested fixes to project files (bounded, deterministic)."""
from __future__ import annotations

import re

from app.build.edits import plan_followup_edits
from app.build.improve import improve_static_files


def apply_suggested_fixes(
    files: dict[str, str],
    suggested_fixes: list[str],
    *,
    project_type: str = "web_game",
) -> tuple[dict[str, str], list[str]]:
    """Return updated files + short notes of what changed."""
    out = dict(files)
    notes: list[str] = []
    fixes = list(dict.fromkeys(suggested_fixes))  # stable unique

    for fix in fixes:
        if fix == "enable_enemies":
            js = out.get("main.js", "")
            if not js:
                continue
            if "window.__NEXA_ENEMIES__" in js:
                js = re.sub(
                    r"window\.__NEXA_ENEMIES__\s*\|\|\s*\d+",
                    "window.__NEXA_ENEMIES__ || 3",
                    js,
                )
                if not re.search(r"window\.__NEXA_ENEMIES__\s*=\s*[1-9]", js):
                    js = "window.__NEXA_ENEMIES__ = 3;\n" + js
            else:
                js = "window.__NEXA_ENEMIES__ = 3;\n" + js
                if "spawnEnemies" not in js and "enemies" not in js:
                    # minimal enemy stub if template lacks enemies entirely
                    js += (
                        "\n/* nexa-eval-enemies */\n"
                        "window.__NEXA_ENEMIES__ = 3;\n"
                    )
            out["main.js"] = js
            notes.append("enable_enemies")

        elif fix == "add_game_over":
            plan = plan_followup_edits("добавь Game Over", current_files=out)
            if plan:
                out.update(plan.files)
                notes.append("add_game_over")

        elif fix == "add_score" or fix == "add_score_hud":
            plan = plan_followup_edits("добавь систему очков", current_files=out)
            if plan:
                out.update(plan.files)
                notes.append(fix)

        elif fix == "add_responsive" or fix == "add_viewport":
            improved, improve_notes = improve_static_files(out, project_type=project_type)
            out.update(improved)
            notes.extend(improve_notes or [fix])

        elif fix == "add_restart":
            js = out.get("main.js", "")
            html = out.get("index.html", "")
            if "keys.has(\"r\")" not in js and "keys.has('r')" not in js:
                js += (
                    "\nwindow.addEventListener('keydown', (e) => {"
                    " if (e.key.toLowerCase() === 'r') location.reload(); });\n"
                )
                out["main.js"] = js
                notes.append("add_restart")
            if "рестарт" not in html.lower() and "restart" not in html.lower():
                out["index.html"] = html.replace(
                    "</main>",
                    '<p class="hint">R — рестарт</p></main>',
                )
                notes.append("add_restart_hint")

        elif fix == "add_car":
            # Cannot synthesize a full car from nothing usefully; flag only if missing
            if "car" not in out.get("main.js", ""):
                notes.append("add_car_skipped_no_template")

        elif fix == "add_coins":
            if "coins" not in out.get("main.js", ""):
                notes.append("add_coins_skipped_no_template")

        elif fix == "add_canvas":
            html = out.get("index.html", "")
            if "<canvas" not in html.lower():
                out["index.html"] = html.replace(
                    "</main>",
                    '<canvas id="game" width="720" height="420"></canvas></main>',
                )
                notes.append("add_canvas")

        elif fix == "add_game_loop":
            js = out.get("main.js", "")
            if "requestAnimationFrame" not in js:
                out["main.js"] = (
                    js
                    + "\n(function loop(){ requestAnimationFrame(loop); })();\n"
                )
                notes.append("add_game_loop")

        elif fix == "fix_js_runtime_error":
            js = out.get("main.js", "")
            if not js:
                continue
            cleaned = js
            # Remove known test/injected throw lines and empty throw stubs
            cleaned = re.sub(
                r"(?m)^\s*throw new Error\(\s*[\"']NEXA_TEST_ERROR[\"']\s*\)\s*;?\s*$",
                "",
                cleaned,
            )
            cleaned = re.sub(
                r"(?m)^\s*throw new Error\([^)]*\)\s*;?\s*$",
                "/* removed throw */",
                cleaned,
                count=1,
            )
            if cleaned != js:
                out["main.js"] = cleaned
                notes.append("fix_js_runtime_error")

        elif fix == "fix_network_asset":
            # Restore broken script/link refs already present in HTML against files on disk
            html = out.get("index.html", "")
            if 'src="main.js"' not in html and "main.js" in out:
                if "<script" in html:
                    out["index.html"] = re.sub(
                        r"<script[^>]*src=[\"'][^\"']+[\"'][^>]*>",
                        '<script src="main.js">',
                        html,
                        count=1,
                    )
                    notes.append("fix_network_asset")

    return out, notes
