"""Real web search via DuckDuckGo's Lite HTML endpoint.
No API key required, no CAPTCHA bypass, no site-restriction bypass —
DDG Lite (``https://lite.duckduckgo.com/html/``) is a public, lightweight search page
meant to be used without JavaScript. We parse its result HTML with regex
(no new dependencies needed).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

from app.web.models import SearchResult
from app.web.search_provider import SearchProvider

# Matches: <a ... class="result__a" href="URL">TITLE</a>
_RESULT_LINK_RE = re.compile(
    r'class="result__a"\s+href="([^"]+)"[^>]*>([^<]+)</a>', re.DOTALL
)
# Matches: <a ... class="result__snippet">SNIPPET</a>
_RESULT_SNIPPET_RE = re.compile(
    r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL
)


def unwrap_ddg_url(raw: str, *, base: str = "https://lite.duckduckgo.com") -> str | None:
    """Turn DDG redirect / relative hrefs into a real http(s) destination."""
    if not raw or not isinstance(raw, str):
        return None
    href = raw.strip()
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = urljoin(base, href)
    parsed = urlparse(href)
    if "duckduckgo.com" in (parsed.netloc or "") and "uddg" in (parsed.query or ""):
        qs = parse_qs(parsed.query)
        target = (qs.get("uddg") or [None])[0]
        if target:
            href = unquote(target)
            parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return href


class DuckDuckGoSearchProvider(SearchProvider):
    """Real web search using DuckDuckGo Lite — no API key needed."""

    name = "duckduckgo"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        url = "https://lite.duckduckgo.com/html/"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    url,
                    data={"q": query, "kl": "us-en"},
                    headers={"User-Agent": "NEXA-AI/1.0"},
                )
                response.raise_for_status()
        except httpx.TimeoutException:
            return []
        except Exception:
            return []
        html = response.text
        links = _RESULT_LINK_RE.findall(html)
        snippets = _RESULT_SNIPPET_RE.findall(html)
        results: list[SearchResult] = []
        for i, (link_url, title) in enumerate(links):
            if len(results) >= max_results:
                break
            resolved = unwrap_ddg_url(link_url)
            if not resolved:
                continue
            title = title.replace("&#x27;", "'").replace("&amp;", "&").strip()
            snippet = ""
            if i < len(snippets):
                snippet = snippets[i]
                snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            results.append(
                SearchResult(title=title, url=resolved, snippet=snippet, source="duckduckgo")
            )
        return results

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get("https://lite.duckduckgo.com/html/")
                return response.status_code < 500
        except Exception:
            return False
