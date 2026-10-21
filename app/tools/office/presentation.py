"""PresentationTool — create real PPTX files with editable shapes."""
from __future__ import annotations

import io
from typing import Any

from app.tools.base import Tool, ToolResult
from app.tools.office.outline import coerce_slides
from app.tools.office.result_store import ResultStore
from app.tools.office.runner import run_office_job


class PresentationTool(Tool):
    name = "create_presentation"
    description = (
        "Create a professional PowerPoint (.pptx) file with title and content slides. "
        "Returns a download_url — never claims PowerPoint was opened on the desktop."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Presentation title."},
            "slides": {
                "type": "array",
                "description": "Optional list of {title, bullets[]} slides.",
            },
            "outline": {
                "type": "string",
                "description": "Free-text outline if slides are not provided.",
            },
            "source_text": {
                "type": "string",
                "description": "Source material to structure into slides.",
            },
            "filename": {"type": "string", "description": "Optional output filename."},
            "include_chart": {
                "type": "boolean",
                "description": "Add a simple bar chart slide when useful.",
            },
            "slide_count": {
                "type": "integer",
                "description": "Target number of content slides (1-20), excluding title slide.",
            },
            "chart_labels": {"type": "array", "items": {"type": "string"}},
            "chart_values": {"type": "array", "items": {"type": "number"}},
            "task_id": {"type": "string"},
            "user_id": {"type": "string"},
        },
        "required": [],
    }
    permissions = frozenset({"filesystem:write"})

    def __init__(self, store: ResultStore) -> None:
        self._store = store

    async def execute(self, **kwargs: Any) -> ToolResult:
        title = str(kwargs.get("title") or "").strip()
        outline = kwargs.get("outline")
        source_text = kwargs.get("source_text")
        slides_in = kwargs.get("slides")
        filename = str(kwargs.get("filename") or title or "presentation")
        include_chart = bool(kwargs.get("include_chart"))
        chart_labels = kwargs.get("chart_labels")
        chart_values = kwargs.get("chart_values")
        slide_count = kwargs.get("slide_count")
        if isinstance(slide_count, str) and slide_count.isdigit():
            slide_count = int(slide_count)
        if not isinstance(slide_count, int):
            slide_count = None

        if not title and not outline and not source_text and not slides_in:
            return ToolResult(
                success=False,
                error="Provide title, outline, source_text, or slides to create a presentation.",
                metadata={"status": "invalid_input"},
            )

        if not title:
            title = "Presentation"

        slides = coerce_slides(
            slides_in or outline,
            title=title,
            source_text=source_text,
            slide_count=slide_count,
        )
        if len(slides) < 1:
            return ToolResult(
                success=False,
                error="Could not build any slides from the provided input.",
                metadata={"status": "invalid_input"},
            )

        async def _build(_tid: str) -> tuple[bytes, str, str, dict[str, Any]]:
            data = _build_pptx(
                title=title,
                slides=slides,
                include_chart=include_chart,
                chart_labels=chart_labels if isinstance(chart_labels, list) else None,
                chart_values=chart_values if isinstance(chart_values, list) else None,
            )
            meta = {
                "slides": len(slides) + (1 if include_chart and chart_labels and chart_values else 0),
                "summary": f"Created PPTX «{title}» with {len(slides)} content slides.",
            }
            return data, filename, "pptx", meta

        return await run_office_job(
            tool_name=self.name,
            store=self._store,
            build=_build,
            task_id=kwargs.get("task_id") if isinstance(kwargs.get("task_id"), str) else None,
            user_id=kwargs.get("user_id") if isinstance(kwargs.get("user_id"), str) else None,
        )


def _build_pptx(
    *,
    title: str,
    slides: list[dict[str, Any]],
    include_chart: bool,
    chart_labels: list | None,
    chart_values: list | None,
) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Title slide
    title_layout = prs.slide_layouts[6]  # blank
    slide0 = prs.slides.add_slide(title_layout)
    _add_bg(slide0, RGBColor(0x12, 0x0A, 0x1F))
    box = slide0.shapes.add_textbox(Inches(0.8), Inches(2.4), Inches(11.5), Inches(1.5))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xE8, 0xE4, 0xFF)
    p.alignment = PP_ALIGN.LEFT
    sub = slide0.shapes.add_textbox(Inches(0.8), Inches(4.1), Inches(11.5), Inches(0.6))
    sp = sub.text_frame.paragraphs[0]
    sp.text = "NEXA AI · HEXARI"
    sp.font.size = Pt(16)
    sp.font.color.rgb = RGBColor(0x7B, 0x8C, 0xFF)

    body_layout = prs.slide_layouts[6]
    for item in slides:
        s = prs.slides.add_slide(body_layout)
        _add_bg(s, RGBColor(0x16, 0x12, 0x24))
        bar = s.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0),
            Inches(0),
            Inches(0.15),
            Inches(7.5),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(0x3B, 0x82, 0xF6)
        bar.line.fill.background()

        h = s.shapes.add_textbox(Inches(0.7), Inches(0.45), Inches(11.8), Inches(0.9))
        hp = h.text_frame.paragraphs[0]
        hp.text = str(item.get("title") or "Slide")
        hp.font.size = Pt(28)
        hp.font.bold = True
        hp.font.color.rgb = RGBColor(0xF3, 0xF0, 0xFF)

        body = s.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(11.8), Inches(5.4))
        tf = body.text_frame
        tf.word_wrap = True
        bullets = item.get("bullets") or []
        if not bullets:
            bullets = [" "]
        for i, bullet in enumerate(bullets):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = str(bullet)
            para.level = 0
            para.font.size = Pt(18)
            para.font.color.rgb = RGBColor(0xD8, 0xD4, 0xEE)
            para.space_after = Pt(10)

    if include_chart and chart_labels and chart_values and len(chart_labels) == len(chart_values):
        _add_chart_slide(prs, chart_labels, chart_values)

    buf = io.BytesIO()
    prs.save(buf)
    data = buf.getvalue()
    if len(data) < 1000:
        raise ValueError("Generated PPTX appears too small to be valid.")
    return data


def _add_bg(slide, color) -> None:
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    # Send to back
    sp_tree = slide.shapes._spTree
    sp = shape._element
    sp_tree.remove(sp)
    sp_tree.insert(2, sp)


def _add_chart_slide(prs, labels: list, values: list) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches, Pt

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_bg(slide, RGBColor(0x16, 0x12, 0x24))
    h = slide.shapes.add_textbox(Inches(0.7), Inches(0.4), Inches(11.8), Inches(0.7))
    hp = h.text_frame.paragraphs[0]
    hp.text = "Overview chart"
    hp.font.size = Pt(28)
    hp.font.bold = True
    hp.font.color.rgb = RGBColor(0xF3, 0xF0, 0xFF)

    chart_data = CategoryChartData()
    chart_data.categories = [str(x) for x in labels][:12]
    nums: list[float] = []
    for v in values[:12]:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            nums.append(0.0)
    chart_data.add_series("Value", nums)
    slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(1.0),
        Inches(1.4),
        Inches(11.0),
        Inches(5.4),
        chart_data,
    )


def verify_pptx_bytes(data: bytes) -> dict[str, Any]:
    """Open PPTX from bytes and return slide count / titles (for tests)."""
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    titles: list[str] = []
    for slide in prs.slides:
        title = ""
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if text:
                title = text.splitlines()[0][:120]
                break
        titles.append(title)
    return {"slide_count": len(prs.slides), "titles": titles}
