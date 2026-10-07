"""``ResearchTool`` - search the web, fetch relevant pages, and return sources.
Implements the same :class:`app.tools.base.Tool` interface used by Part 2's
agent tools, so it can be registered into a :class:`app.tools.registry.ToolRegistry`
and used by the Agent exactly like ``calculator`` or ``file_write``.
"""
from __future__ import annotations
from app.core.logging_config import get_logger
from app.models.errors import NexaError
from app.tools.base import Tool, ToolResult
from app.web.content_extractor import ContentExtractor
from app.web.models import PageDocument, SearchResult
from app.web.page_fetcher import PageFetcher
from app.web.search_provider import SearchProvider
from app.web.source_manager import SourceManager
logger = get_logger("nexa.web.research")
class ResearchTool(Tool):
    name = "web_research"
    description = (
        "Search the web for a query, fetch the most relevant pages, and "
        "return their extracted text as sources."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results to fetch (default provider-configured).",
            },
        },
        "required": ["query"],
    }
    permissions = frozenset({"network:read"})
    def __init__(
        self,
        search_provider: SearchProvider,
        page_fetcher: PageFetcher,
        source_manager: SourceManager | None = None,
        content_extractor: ContentExtractor | None = None,
        default_max_results: int = 5,
    ) -> None:
        self._search_provider = search_provider
        self._page_fetcher = page_fetcher
        self._source_manager = source_manager or SourceManager()
        self._content_extractor = content_extractor or ContentExtractor()
        self._default_max_results = default_max_results
    # --- the four required capabilities -----------------------------------
    async def search(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        """Search the web for ``query``."""
        return await self._search_provider.search(
            query, max_results=max_results or self._default_max_results
        )
    async def fetch(self, url: str) -> PageDocument:
        """Fetch and extract the content of a single page."""
        document = await self._page_fetcher.fetch(url)
        self._source_manager.add(document)
        return document
    def extract(self, html: str) -> tuple[str, str]:
        """Extract ``(title, text)`` from raw HTML (without fetching anything)."""
        return self._content_extractor.extract(html)
    def sources(self) -> list[PageDocument]:
        """Return every page document collected so far by this tool instance."""
        return self._source_manager.get_all()
    # --- Tool interface ----------------------------------------------------
    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query")
        max_results = kwargs.get("max_results")
        if not query or not isinstance(query, str):
            return ToolResult(success=False, error="'query' must be a non-empty string.")
        try:
            results = await self.search(query, max_results=max_results)
        except NexaError as exc:
            return ToolResult(success=False, error=str(exc))
        fetched: list[PageDocument] = []
        errors: list[str] = []
        for result in results:
            try:
                fetched.append(await self.fetch(result.url))
            except NexaError as exc:
                logger.warning("skipping source %s: %s", result.url, exc.message)
                errors.append(f"{result.url}: {exc.message}")
        return ToolResult(
            success=True,
            output={
                "query": query,
                "results": [r.model_dump(mode="json") for r in results],
                "sources": [d.model_dump(mode="json") for d in fetched],
            },
            metadata={"skipped": errors} if errors else {},
        )
