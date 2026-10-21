"""Shared HTML/CSS shell for Three.js CDN game templates (Part 13)."""
from __future__ import annotations

THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"


def index_html(*, title: str, subtitle: str, hud_extra: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} — NEXA</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
    <div class="hud" id="hud">
      <span id="status">Готово</span>
      <span id="score">0</span>
      {hud_extra}
    </div>
    <div id="game-wrap">
      <canvas id="game" tabindex="0" aria-label="3D сцена"></canvas>
      <div id="overlay" class="hidden"><p id="overlay-text"></p><button type="button" id="restart">Заново</button></div>
    </div>
  </main>
  <script src="{THREE_CDN}"></script>
  <script src="main.js"></script>
</body>
</html>
"""


STYLE_CSS = """:root {
  color-scheme: dark;
  --bg: #07070f;
  --panel: #141428;
  --accent: #7a5cff;
  --cyan: #5ad0ff;
  --text: #e8eef7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: radial-gradient(ellipse at top, #1a1430, var(--bg));
  color: var(--text);
}
main { width: min(960px, 96vw); }
header h1 { margin: 0 0 0.2rem; font-size: 1.35rem; }
header p { margin: 0 0 0.75rem; opacity: 0.7; font-size: 0.88rem; }
.hud {
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
  padding: 0.55rem 0.8rem;
  background: var(--panel);
  border: 1px solid rgba(122, 92, 255, 0.25);
  border-radius: 10px;
  font-variant-numeric: tabular-nums;
}
#game-wrap {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(0,0,0,0.45);
  border: 1px solid rgba(90, 208, 255, 0.2);
}
#game {
  display: block;
  width: 100%;
  height: min(56vh, 520px);
  background: #05050a;
  outline: none;
}
#overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(5, 5, 12, 0.72);
  text-align: center;
  padding: 1rem;
}
#overlay.hidden { display: none; }
#overlay button {
  margin-top: 0.75rem;
  padding: 0.55rem 1.1rem;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--cyan), var(--accent));
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
"""


def scene_json(*, genre: str, objects: list[dict]) -> str:
    import json

    return json.dumps(
        {
            "engine": "three.js",
            "cdn": THREE_CDN,
            "genre": genre,
            "objects": objects,
        },
        ensure_ascii=False,
        indent=2,
    )
