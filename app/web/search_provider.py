"""Search provider abstraction for web research.
Mirrors the ``AIProvider`` / ``ProviderFactory`` pattern from Part 1: NEXA
never depends on a specific search backend, only on the ``SearchProvider``
interface. ``HttpSearchProvider`` is a generic adapter for any JSON search
API (configured via ``SEARCH_API_URL`` / ``SEARCH_API_KEY``) - NEXA does not
ship a scraper for any specific search engine, to respect each site's terms
of service (no CAPTCHA bypass, no bypassing site restrictions).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import httpx
from app.models.errors import ProviderConfigurationError, SearchError
from app.web.models import SearchResult
class SearchProvider(ABC):
    """Abstract interface for a web search backend."""
    name: str = "base"
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Return up to ``max_results`` search results for ``query``."""
    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable/configured."""
class MockSearchProvider(SearchProvider):
    """Deterministic, offline search provider - the default for local dev/tests."""
    name = "mock"
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        count = max(0, min(max_results, 5))
        # Points at example.com's root ("/") on purpose: it is a stable,
        # always-200 domain reserved by IANA for documentation/testing, so
        # a real PageFetcher.fetch() against a mock result actually succeeds.
        return [
            SearchResult(
                title=f"Mock result {i + 1} for '{query}'",
                url=f"https://example.com/?q={query.replace(' ', '+')}&result={i + 1}",
                snippet=f"This is a mock search snippet #{i + 1} about '{query}'.",
                source="mock",
            )
            for i in range(count)
        ]
    async def health_check(self) -> bool:
        return True
class HttpSearchProvider(SearchProvider):
    """Adapter for a generic JSON search API.
    Expects the configured endpoint to return a JSON array of objects with
    ``title``, ``url`` and (optionally) ``snippet`` fields - the same
    "bring your own endpoint" shape used by :class:`app.providers.local_provider.LocalProvider`
    in Part 1.
    """
    name = "http"
    def __init__(self, api_url: str | None, api_key: str | None = None, timeout_seconds: float = 10.0) -> None:
        if not api_url:
            raise ProviderConfigurationError(
                "SEARCH_API_URL is not set. Configure it in your .env file to use AI_PROVIDER=http search."
            )
        self._api_url = api_url
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
    def _headers(self) -> dict:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    self._api_url,
                    params={"q": query, "num": max_results},
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise SearchError(f"Search request failed: {exc}") from exc
        except ValueError as exc:
            raise SearchError(f"Search provider returned invalid JSON: {exc}") from exc
        items = data if isinstance(data, list) else data.get("results", [])
        results = []
        for item in items[:max_results]:
            try:
                results.append(
                    SearchResult(
                        title=item["title"],
                        url=item["url"],
                        snippet=item.get("snippet", ""),
                        source=self.name,
                    )
                )
            except (KeyError, TypeError) as exc:
                raise SearchError(f"Malformed search result from provider: {exc}") from exc
        return results
    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(self._api_url, headers=self._headers())
                return response.status_code < 500
        except Exception:  # noqa: BLE001
            return False
class SearchProviderFactory:
    """Selects a :class:`SearchProvider` implementation based on configuration."""
    @staticmethod
    def create(
        provider_name: str,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> SearchProvider:
        name = (provider_name or "mock").strip().lower()
        if name == "mock":
            return MockSearchProvider()
        if name == "http":
            return HttpSearchProvider(api_url=api_url, api_key=api_key, timeout_seconds=timeout_seconds)
        if name == "duckduckgo":
            from app.web.duckduckgo_provider import DuckDuckGoSearchProvider
            return DuckDuckGoSearchProvider(timeout_seconds=timeout_seconds)
        raise ProviderConfigurationError(f"Unknown web search provider '{name}'.")
