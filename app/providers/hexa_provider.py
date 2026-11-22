"""First-party HEXA 4.5 inference adapter.

The model weights are hosted by a separately managed Ollama-compatible
inference server. This adapter does not claim that model weights are included
in the NEXA application.
"""
from __future__ import annotations

from app.models.errors import ProviderConfigurationError
from app.providers.local_provider import LocalProvider


class Hexa45Provider(LocalProvider):
    """Route requests to the configured HEXA inference endpoint."""

    name = "hexa"

    def __init__(
        self,
        base_url: str | None,
        model: str = "hexa-4.5",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ProviderConfigurationError(
                "HEXA_MODEL_URL is not configured. Set it to the HEXA inference server URL."
            )
        super().__init__(
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )
