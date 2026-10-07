#!/usr/bin/env python3
"""NEXA Web Research demo (Part 3).
Runs the ResearchTool end-to-end with the default (mock) search provider and
a *real* PageFetcher - this makes a genuine outbound HTTP request (to
example.com, which is what MockSearchProvider points at) so you can see the
SSRF-protected fetch + extraction pipeline work against the real network.
Usage:
    python scripts/demo_research.py "your query here"
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config.settings import get_settings  # noqa: E402
from app.web.page_fetcher import PageFetcher  # noqa: E402
from app.web.research_tool import ResearchTool  # noqa: E402
from app.web.search_provider import SearchProviderFactory  # noqa: E402
async def main(query: str) -> int:
    settings = get_settings()
    search_provider = SearchProviderFactory.create(
        settings.web_search_provider,
        api_url=settings.search_api_url,
        api_key=settings.search_api_key,
        timeout_seconds=settings.web_fetch_timeout_seconds,
    )
    page_fetcher = PageFetcher(
        timeout_seconds=settings.web_fetch_timeout_seconds,
        max_page_size_bytes=settings.web_max_page_size_bytes,
        max_redirects=settings.web_max_redirects,
    )
    tool = ResearchTool(
        search_provider=search_provider,
        page_fetcher=page_fetcher,
        default_max_results=min(2, settings.web_max_search_results),
    )
    print(f"Search provider: {search_provider.name}")
    print(f"Query: {query}\n")
    result = await tool.execute(query=query)
    print(json.dumps(result.output, indent=2, ensure_ascii=False, default=str))
    if result.metadata.get("skipped"):
        print("\nSkipped sources:", result.metadata["skipped"])
    return 0 if result.success else 1
if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "NEXA AI platform"
    raise SystemExit(asyncio.run(main(query)))
