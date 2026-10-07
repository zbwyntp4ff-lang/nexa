"""Post-success IMPROVE pass — small safe polish, no speculative rewrites."""
from __future__ import annotations

import re


def improve_static_files(files: dict[str, str], *, project_type: str) -> tuple[dict[str, str], list[str]]:
    """Return patched files + list of improvements applied."""
    out = dict(files)
    notes: list[str] = []

    css = out.get("style.css", "")
    if css and "/* nexa-v2-improve */" not in css:
        out["style.css"] = (
            css
            + "\n/* nexa-v2-improve */\n"
            + "@media (max-width: 640px) {\n"
            + "  main { width: 96vw; }\n"
            + "  header h1 { font-size: 1.25rem; }\n"
            + "}\n"
        )
        notes.append("responsive tweaks")

    html = out.get("index.html", "")
    if html and 'lang="' in html and "viewport" not in html.lower():
        out["index.html"] = html.replace(
            "<head>",
            '<head>\n  <meta name="viewport" content="width=device-width, initial-scale=1" />',
            1,
        )
        notes.append("viewport meta")

    if project_type == "web_game":
        js = out.get("main.js", "")
        if js and "tabindex" not in html and "<canvas" in html:
            out["index.html"] = re.sub(
                r"<canvas([^>]*)>",
                r'<canvas\1 tabindex="0">',
                out.get("index.html", html),
                count=1,
            )
            notes.append("canvas focusable for keyboard")

    return out, notes
