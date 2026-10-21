"""Shared outline parsing for generated office documents."""
from __future__ import annotations

import re
from typing import Any


def coerce_slides(
    raw: Any,
    *,
    title: str,
    source_text: str | None = None,
    slide_count: int | None = None,
) -> list[dict[str, Any]]:
    """Normalize slides from list/dict/string into ``[{title, bullets}]``."""
    slides: list[dict[str, Any]] = []
    if isinstance(raw, list) and raw:
        for i, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                slide_title = str(item.get("title") or f"Slide {i}").strip()
                bullets = item.get("bullets") or item.get("points") or item.get("body")
                if isinstance(bullets, str):
                    bullets = [b.strip() for b in bullets.split("\n") if b.strip()]
                elif isinstance(bullets, list):
                    bullets = [str(b).strip() for b in bullets if str(b).strip()]
                else:
                    bullets = []
                slides.append({"title": slide_title[:200], "bullets": bullets[:12]})
            elif isinstance(item, str) and item.strip():
                slides.append({"title": item.strip()[:200], "bullets": []})

    if not slides:
        text = ""
        if isinstance(raw, str) and raw.strip():
            text = raw.strip()
        elif source_text and source_text.strip():
            text = source_text.strip()
        elif title.strip():
            text = title.strip()
        slides = outline_from_text(text, fallback_title=title or "Presentation")

    if slide_count is not None and slide_count > 0:
        slides = _fit_slide_count(slides, slide_count, title=title or "Presentation")
    return slides


def _fit_slide_count(
    slides: list[dict[str, Any]], count: int, *, title: str
) -> list[dict[str, Any]]:
    """Pad or trim content slides to ``count`` (title slide is separate in PPTX builder)."""
    count = max(1, min(int(count), 20))
    if len(slides) > count:
        return slides[:count]
    out = list(slides)
    while len(out) < count:
        i = len(out) + 1
        out.append(
            {
                "title": f"{title}: section {i}"[:200],
                "bullets": [
                    "Key point (expand with research FACTS).",
                    "ASSUMPTION: placeholder — replace with sourced data.",
                ],
            }
        )
    return out


def outline_from_text(text: str, *, fallback_title: str = "Document") -> list[dict[str, Any]]:
    """Build slide/section outline from free text or numbered lists."""
    text = (text or "").strip()
    if not text:
        return [
            {"title": fallback_title, "bullets": ["Add content for this section."]},
            {"title": "Key points", "bullets": ["Point 1", "Point 2", "Point 3"]},
            {"title": "Next steps", "bullets": ["Clarify goals", "Assign owners", "Set timeline"]},
        ]

    # Numbered / markdown sections
    chunks = re.split(r"\n(?=\s*(?:\d+[\.\)]\s+|#{1,3}\s+|[-*•]\s+))", text)
    sections: list[dict[str, Any]] = []
    if len(chunks) >= 2:
        for i, chunk in enumerate(chunks, start=1):
            lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
            if not lines:
                continue
            head = re.sub(r"^(\d+[\.\)]\s+|#{1,3}\s+|[-*•]\s+)", "", lines[0]).strip()
            bullets = [
                re.sub(r"^(\d+[\.\)]\s+|#{1,3}\s+|[-*•]\s+)", "", ln).strip()
                for ln in lines[1:8]
            ]
            bullets = [b for b in bullets if b]
            sections.append({"title": (head or f"Section {i}")[:200], "bullets": bullets})
        if sections:
            return sections[:12]

    # Sentence / paragraph split → up to 6 slides
    paras = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(paras) == 1:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", paras[0]) if s.strip()]
        if len(sentences) >= 3:
            paras = sentences

    if not paras:
        paras = [text]

    title_slide = {"title": fallback_title[:200], "bullets": [paras[0][:240]]}
    body: list[dict[str, Any]] = []
    for i, para in enumerate(paras[:8], start=1):
        body.append(
            {
                "title": f"{fallback_title}: {i}"[:200] if i > 1 or len(paras) > 1 else fallback_title[:200],
                "bullets": _bullets_from_para(para),
            }
        )
    # Prefer a title + content structure without duplicating the first para twice.
    if len(body) == 1:
        return [title_slide, {"title": "Overview", "bullets": body[0]["bullets"]}, {"title": "Summary", "bullets": ["Key takeaway from the brief."]}]
    return [title_slide, *body[1:7]]


def _bullets_from_para(para: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[;\n]|•|\s[-–—]\s", para) if p.strip()]
    if len(parts) >= 2:
        return [p[:220] for p in parts[:8]]
    # Soft wrap long paragraph into ~2 bullets
    if len(para) > 160:
        mid = para.rfind(" ", 0, len(para) // 2)
        if mid > 40:
            return [para[:mid].strip()[:220], para[mid:].strip()[:220]]
    return [para[:220]]


def coerce_sections(raw: Any, *, title: str, source_text: str | None = None) -> list[dict[str, Any]]:
    """Same as slides but used for DOCX/PDF headings."""
    return coerce_slides(raw, title=title, source_text=source_text)


def coerce_table_rows(raw: Any) -> list[list[str]]:
    """Normalize tabular data into rows of strings (first row = header if present)."""
    if isinstance(raw, list) and raw:
        rows: list[list[str]] = []
        for item in raw:
            if isinstance(item, dict):
                if not rows:
                    rows.append([str(k) for k in item.keys()])
                rows.append([str(v) for v in item.values()])
            elif isinstance(item, (list, tuple)):
                rows.append([str(c) for c in item])
            elif isinstance(item, str) and item.strip():
                rows.append([c.strip() for c in re.split(r"[,;\t|]", item) if c.strip()])
        if rows:
            return rows
    if isinstance(raw, str) and raw.strip():
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return [[c.strip() for c in re.split(r"[,;\t|]", ln) if c.strip()] for ln in lines]
    return [
        ["Item", "Value", "Notes"],
        ["Example A", "10", "Replace with your data"],
        ["Example B", "20", "Replace with your data"],
    ]
