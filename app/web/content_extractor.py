"""Extract a title and readable text from raw HTML.
Deliberately dependency-free (uses the standard library's ``html.parser``)
rather than pulling in a full HTML/JS execution engine - NEXA only ever
reads text, it never executes scripts or renders pages.
"""
from __future__ import annotations
from html.parser import HTMLParser
class _TextExtractingParser(HTMLParser):
    _SKIP_TAGS = frozenset({"script", "style", "noscript", "template"})
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._text_parts.append("\n")
    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
            return
        if self._skip_depth:
            return
        self._text_parts.append(data)
    @property
    def title(self) -> str:
        return "".join(self._title_parts).strip()
    @property
    def text(self) -> str:
        raw = "".join(self._text_parts)
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)
class ContentExtractor:
    """Turns raw HTML into ``(title, text)``."""
    def extract(self, html: str) -> tuple[str, str]:
        parser = _TextExtractingParser()
        parser.feed(html)
        parser.close()
        return parser.title, parser.text
