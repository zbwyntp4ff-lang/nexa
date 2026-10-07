"""Follow-up edits for an existing BUILD_PROJECT workspace."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class EditPlan:
    description: str
    files: dict[str, str]  # relative path -> full new content
    features_added: list[str] | None = None


_ENEMIES = re.compile(r"враг|enemy|enemies", re.IGNORECASE)
_PRETTIER = re.compile(r"красивее|красив|prettier|beautiful|style|дизайн", re.IGNORECASE)
_MUSIC = re.compile(r"музык|music|звук|sound", re.IGNORECASE)
_SHOP = re.compile(r"магазин|shop|store", re.IGNORECASE)
_SCORE = re.compile(r"очк|score|систем\w*\s+очк", re.IGNORECASE)
_GAME_OVER = re.compile(r"game\s*over|гейм\s*овер|конец\s*игр", re.IGNORECASE)


_SCORE_JS_SNIPPET = """
/* nexa-score-system */
window.__NEXA_SCORE__ = window.__NEXA_SCORE__ || { value: 0, best: 0 };
function nexaSetScore(n) {
  window.__NEXA_SCORE__.value = n;
  if (n > (window.__NEXA_SCORE__.best || 0)) window.__NEXA_SCORE__.best = n;
  const el = document.getElementById("score");
  const best = document.getElementById("best-score");
  if (el) el.textContent = "Очки: " + n;
  if (best) best.textContent = "Рекорд: " + window.__NEXA_SCORE__.best;
}
"""

_GAME_OVER_JS_SNIPPET = """
/* nexa-game-over */
function nexaShowGameOver(reason) {
  const overlay = document.getElementById("game-over");
  const reasonEl = document.getElementById("game-over-reason");
  if (reasonEl) reasonEl.textContent = reason || "Game Over";
  if (overlay) overlay.hidden = false;
  const statusEl = document.getElementById("status");
  if (statusEl) statusEl.textContent = "Game Over · R — рестарт";
}
function nexaHideGameOver() {
  const overlay = document.getElementById("game-over");
  if (overlay) overlay.hidden = true;
}
"""


def plan_followup_edits(message: str, *, current_files: dict[str, str]) -> EditPlan | None:
    """Return file patches for a follow-up request, or None if unknown."""
    text = message.strip()
    main_js = current_files.get("main.js", "")
    style_css = current_files.get("style.css", "")
    index_html = current_files.get("index.html", "")
    out: dict[str, str] = {}
    notes: list[str] = []
    features: list[str] = []

    if _ENEMIES.search(text) and main_js:
        if "window.__NEXA_ENEMIES__" in main_js:
            patched = out.get("main.js", main_js)
            patched = re.sub(
                r"window\.__NEXA_ENEMIES__\s*\|\|\s*\d+",
                "window.__NEXA_ENEMIES__ || 3",
                patched,
            )
            if "window.__NEXA_ENEMIES__ = 3" not in patched:
                patched = "window.__NEXA_ENEMIES__ = 3;\n" + patched
            out["main.js"] = patched
            notes.append("добавлены враги")
            features.append("enemies")
        else:
            return None

    if _SCORE.search(text) and (main_js or index_html):
        js = out.get("main.js", main_js)
        html = out.get("index.html", index_html)
        if "nexa-score-system" not in js:
            # Hook score updates where score is incremented
            js = _SCORE_JS_SNIPPET + "\n" + js
            js = js.replace(
                'scoreEl.textContent = "Монеты: " + score;',
                'nexaSetScore(score);',
            )
            js = js.replace(
                'scoreEl.textContent = "Монеты: 0";',
                'nexaSetScore(0);',
            )
            out["main.js"] = js
        if html and 'id="best-score"' not in html:
            html = html.replace(
                '<span id="score">Монеты: 0</span>',
                '<span id="score">Очки: 0</span><span id="best-score">Рекорд: 0</span>',
            )
            out["index.html"] = html
        notes.append("система очков")
        features.append("score_system")

    if _GAME_OVER.search(text) and (main_js or index_html):
        js = out.get("main.js", main_js)
        html = out.get("index.html", index_html)
        css = out.get("style.css", style_css)
        if "nexa-game-over" not in js:
            js = _GAME_OVER_JS_SNIPPET + "\n" + js
            # Collision / death path
            js = js.replace(
                'statusEl.textContent = "Столкновение! R — рестарт";',
                'nexaShowGameOver("Столкновение с врагом");',
            )
            # Reset should hide overlay
            if "function reset()" in js and "nexaHideGameOver" not in js:
                js = js.replace("function reset() {", "function reset() {\n    nexaHideGameOver();")
            out["main.js"] = js
        if html and 'id="game-over"' not in html:
            html = html.replace(
                '<canvas id="game"',
                '<div id="game-over" hidden class="game-over">'
                "<h2>Game Over</h2>"
                '<p id="game-over-reason"></p>'
                "<p>Нажми R для рестарта</p>"
                "</div>\n    <canvas id=\"game\"",
            )
            out["index.html"] = html
        if css and "/* nexa-game-over */" not in css:
            out["style.css"] = (
                css
                + "\n/* nexa-game-over */\n"
                + "main { position: relative; }\n"
                + ".game-over {\n"
                + "  position: absolute; inset: 4.5rem 0 0; display: grid; place-items: center;\n"
                + "  background: rgba(8,12,18,0.72); border-radius: 12px; text-align: center; z-index: 2;\n"
                + "}\n"
                + ".game-over[hidden] { display: none; }\n"
            )
        notes.append("Game Over экран")
        features.append("game_over")

    if _PRETTIER.search(text) and style_css:
        css = out.get("style.css", style_css)
        if "/* nexa-pretty */" not in css:
            out["style.css"] = (
                css
                + "\n/* nexa-pretty */\n"
                + "body { background: radial-gradient(ellipse at 30% 0%, #243447, #0b1018 70%); }\n"
                + "#game { box-shadow: 0 18px 50px rgba(61,214,198,0.18), 0 12px 40px rgba(0,0,0,0.4); }\n"
                + "header h1 { letter-spacing: 0.04em; color: #7ff0e4; }\n"
            )
            notes.append("обновлён визуальный стиль")
            features.append("visual_polish")

    if _MUSIC.search(text) and index_html and main_js:
        html = out.get("index.html", index_html)
        if 'id="music-btn"' not in html and 'id="bgm"' not in html:
            out["index.html"] = html.replace(
                '<script src="main.js"></script>',
                '<button id="music-btn" type="button" style="margin-top:0.75rem">Музыка</button>\n'
                '  <script src="main.js"></script>',
            )
        js = out.get("main.js", main_js)
        if "AudioContext" not in js:
            out["main.js"] = (
                js
                + "\n(() => {\n"
                + "  let ctx, osc, gain, on = false;\n"
                + "  const btn = document.getElementById('music-btn');\n"
                + "  function start() {\n"
                + "    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();\n"
                + "    osc = ctx.createOscillator(); gain = ctx.createGain();\n"
                + "    osc.type = 'triangle'; osc.frequency.value = 196;\n"
                + "    gain.gain.value = 0.03; osc.connect(gain); gain.connect(ctx.destination); osc.start();\n"
                + "    on = true; if (btn) btn.textContent = 'Стоп музыка';\n"
                + "  }\n"
                + "  function stop() { try { osc.stop(); } catch (_) {} on = false; if (btn) btn.textContent = 'Музыка'; }\n"
                + "  btn?.addEventListener('click', () => on ? stop() : start());\n"
                + "})();\n"
            )
            notes.append("добавлена кнопка музыки")
            features.append("music")

    if _SHOP.search(text) and index_html:
        html = out.get("index.html", index_html)
        if 'id="shop"' not in html:
            out["index.html"] = html.replace(
                '<div class="hud">',
                '<div id="shop" class="hud" style="margin-bottom:0.35rem">'
                "<span>Магазин:</span><span>Скин машины — скоро</span></div>\n"
                '    <div class="hud">',
            )
            notes.append("добавлен блок магазина")
            features.append("shop")

    if not out:
        return None
    return EditPlan(
        description="; ".join(notes) or "правки",
        files=out,
        features_added=features or None,
    )
