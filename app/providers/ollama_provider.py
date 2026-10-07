"""Ollama provider.
This is the existing local-server adapter (:class:`LocalProvider`) under the
provider name ``ollama``. The HTTP protocol (``POST /api/chat``, NDJSON
streaming, ``GET /`` health) is unchanged, so a server that already works
with ``AI_PROVIDER=local`` keeps working.
"""
from __future__ import annotations
import httpx
from app.providers.local_provider import LocalProvider
class OllamaProvider(LocalProvider):
    """LocalProvider addressed as the Ollama provider."""
    name = "ollama"
async def fetch_installed_models(base_url: str, timeout_seconds: float = 2.0) -> list[str]:
    """Return model names reported by a running Ollama server (``GET /api/tags``).
    Raises:
        httpx.HTTPError: If the server cannot be reached.
    """
    url = f"{base_url.rstrip('/')}/api/tags"
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    models = data.get("models", []) if isinstance(data, dict) else []
    names: list[str] = []
    for item in models:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names
