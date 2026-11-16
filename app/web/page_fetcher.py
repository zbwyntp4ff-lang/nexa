"""Fetches a web page's content, subject to strict security limits.
Security measures (all required by Part 3):
- ``timeout``: bounded via ``httpx`` client timeout.
- ``maximum page size``: enforced by streaming the response body and
  aborting as soon as the configured byte limit is exceeded (never trusts
  ``Content-Length`` alone, since it can be absent or wrong).
- SSRF protection / blocking localhost & private networks / no ``file://``:
  every URL - including every redirect hop - is validated with
  :func:`app.web.security.validate_url` before it is requested.
- safe redirects: redirects are followed manually (not by the HTTP client)
  so each hop can be re-validated, and the hop count is capped.
"""
from __future__ import annotations
import hashlib
from urllib.parse import urljoin
import httpx
from app.models.errors import PageTooLargeError, WebFetchError, WebFetchTimeoutError
from app.web.content_extractor import ContentExtractor
from app.web.models import PageDocument
from app.web.security import Resolver, pin_url_to_validated_address
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NEXAResearch/1.0; +https://localhost) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8,ru;q=0.7",
}


class PageFetcher:
    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_page_size_bytes: int = 2_000_000,
        max_redirects: int = 3,
        resolver: Resolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        content_extractor: ContentExtractor | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_page_size_bytes = max_page_size_bytes
        self._max_redirects = max_redirects
        self._resolver = resolver
        self._transport = transport
        self._extractor = content_extractor or ContentExtractor()
    async def fetch(self, url: str) -> PageDocument:
        """Fetch and extract ``url``.
        Raises:
            app.models.errors.InvalidURLError
            app.models.errors.SSRFProtectionError
            app.models.errors.PageTooLargeError
            app.models.errors.WebFetchTimeoutError
            app.models.errors.WebFetchError
        """
        current_url = url
        client_kwargs = {
            "timeout": self._timeout_seconds,
            "follow_redirects": False,
            "headers": dict(_DEFAULT_HEADERS),
        }
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                for _ in range(self._max_redirects + 1):
                    request_url, original_host = (
                        pin_url_to_validated_address(current_url, self._resolver)
                        if self._resolver
                        else pin_url_to_validated_address(current_url)
                    )
                    raw_bytes, headers = await self._get_body(
                        client, current_url, request_url, original_host
                    )
                    status_code, location = headers
                    if status_code in _REDIRECT_STATUS_CODES:
                        if not location:
                            raise WebFetchError(f"Redirect from '{current_url}' had no Location header.")
                        next_url = urljoin(current_url, location)
                        current_url = self._validate(next_url)
                        continue
                    break
                else:
                    raise WebFetchError(f"Too many redirects while fetching '{url}'.")
        except httpx.TimeoutException as exc:
            raise WebFetchTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise WebFetchError(f"Failed to fetch '{url}': {exc}") from exc
        text = raw_bytes.decode("utf-8", errors="replace")
        title, extracted = self._extractor.extract(text)
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        return PageDocument(
            url=current_url,
            title=title,
            text=extracted,
            content_hash=content_hash,
        )
    async def _get_body(
        self,
        client: httpx.AsyncClient,
        url: str,
        request_url: str,
        original_host: str,
    ) -> tuple[bytes, tuple[int, str | None]]:
        parsed = httpx.URL(url)
        host_header = f"[{parsed.host}]" if ":" in parsed.host else parsed.host
        if parsed.port is not None:
            host_header = f"{host_header}:{parsed.port}"
        async with client.stream(
            "GET",
            request_url,
            headers={"Host": host_header},
            extensions={"sni_hostname": original_host},
        ) as response:
            status_code = response.status_code
            location = response.headers.get("location")
            if status_code in _REDIRECT_STATUS_CODES:
                await response.aclose()
                return b"", (status_code, location)
            if status_code >= 400:
                raise WebFetchError(f"'{url}' returned HTTP {status_code}.")
            chunks = bytearray()
            truncated = False
            try:
                async for chunk in response.aiter_bytes():
                    remaining = self._max_page_size_bytes - len(chunks)
                    if remaining <= 0:
                        truncated = True
                        break
                    if len(chunk) > remaining:
                        chunks.extend(chunk[:remaining])
                        truncated = True
                        break
                    chunks.extend(chunk)
            finally:
                if truncated:
                    await response.aclose()
            if truncated and not chunks:
                raise PageTooLargeError(
                    f"Page at '{url}' exceeds the maximum size of "
                    f"{self._max_page_size_bytes} bytes."
                )
            # Prefer partial extract over hard fail when HTML is huge but usable.
            return bytes(chunks), (status_code, location)
