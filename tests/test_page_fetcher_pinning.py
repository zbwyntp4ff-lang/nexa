"""DNS pinning tests for the web research fetcher."""
from __future__ import annotations

import socket

import httpx
import pytest

from app.models.errors import SSRFProtectionError
from app.web.page_fetcher import PageFetcher


def _dns_result(address: str, port: int | None):
    return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port or 443))


@pytest.mark.asyncio
async def test_fetch_connects_to_validated_ip_but_preserves_host_and_sni():
    observed = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["host"] = request.url.host
        observed["header"] = request.headers.get("host")
        observed["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, text="<html><title>Safe</title><body>Public content</body></html>")

    def resolver(hostname: str, port: int | None = None):
        assert hostname == "public.example"
        return [_dns_result("93.184.216.34", port)]

    fetcher = PageFetcher(
        resolver=resolver,
        transport=httpx.MockTransport(handler),
    )
    document = await fetcher.fetch("https://public.example/path")
    assert observed == {
        "host": "93.184.216.34",
        "header": "public.example",
        "sni": "public.example",
    }
    assert document.title == "Safe"


@pytest.mark.asyncio
async def test_fetch_rejects_dns_rebinding_before_socket_connect():
    calls = 0

    def resolver(hostname: str, port: int | None = None):
        nonlocal calls
        calls += 1
        address = "93.184.216.34" if calls == 1 else "127.0.0.1"
        return [_dns_result(address, port)]

    async def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("No request may be sent after the DNS answer changes to loopback")

    fetcher = PageFetcher(
        resolver=resolver,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SSRFProtectionError):
        await fetcher.fetch("https://rebind.example/")
