"""Minimal static HTML site (no npm)."""
from __future__ import annotations

import html


def files_for_static_site(prompt: str) -> dict[str, str]:
    safe = html.escape(prompt.strip()[:240] or "Новый сайт")
    index = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NEXA Site</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <main>
    <h1>NEXA Site</h1>
    <p class="lead">Проект создан по запросу:</p>
    <blockquote>{safe}</blockquote>
    <button id="cta" type="button">Нажми меня</button>
    <p id="out" hidden>Работает.</p>
  </main>
  <script src="main.js"></script>
</body>
</html>
"""
    css = """:root {
  color-scheme: light;
  --bg: #f3f6fb;
  --ink: #142033;
  --accent: #1f6feb;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: linear-gradient(160deg, #e8eef8, var(--bg));
  color: var(--ink);
}
main {
  width: min(560px, 92vw);
  padding: 2rem;
}
h1 { margin: 0 0 0.5rem; font-size: 2rem; }
.lead { opacity: 0.75; }
blockquote {
  margin: 1rem 0 1.5rem;
  padding: 0.75rem 1rem;
  border-left: 3px solid var(--accent);
  background: rgba(31, 111, 235, 0.08);
}
button {
  appearance: none;
  border: 0;
  border-radius: 10px;
  padding: 0.7rem 1.1rem;
  background: var(--accent);
  color: white;
  font: inherit;
  cursor: pointer;
}
#out { margin-top: 1rem; font-weight: 600; }
"""
    js = """document.getElementById("cta")?.addEventListener("click", () => {
  const out = document.getElementById("out");
  if (out) out.hidden = false;
});
"""
    return {
        "index.html": index,
        "style.css": css,
        "main.js": js,
        "README.md": "# NEXA Site\n\nСтатический сайт. Открой `index.html` через preview NEXA.\n",
    }
