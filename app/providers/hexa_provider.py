"""First-party HEXA 4.5 inference provider.

The initial server adapter speaks the Ollama-compatible chat API. Model
weights remain outside the application repository and are loaded by the
configured inference server.
"""
from __future__ import annotations

from app.models.errors import ProviderConfigurationError
from app.providers.local_provider import LocalProvider


class Hexa45Provider(LocalProvider):
    """Route NEXA chat requests to the dedicated HEXA inference endpoint."""

    name = "hexa"

    def __init__(
        self,
        base_url: str | None,
        model: str = "hexa-4.5",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not base_url:
            raise ProviderConfigurationError(
                "HEXA_MODEL_URL is not configured. Set it to the HEXA inference server URL."
            )
        super().__init__(base_url=base_url, model=model, timeout_seconds=timeout_seconds)
