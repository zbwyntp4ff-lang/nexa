"""Google Gemini provider via Generative Language API (httpx).

Requires ``GEMINI_API_KEY`` / ``GOOGLE_API_KEY``. Missing key raises
:class:`ProviderConfigurationError` — never invents a mock reply.
"""
from __future__ import annotations
from collections.abc import AsyncIterator
import httpx
from app.models.chat import ChatMessage, ChatRole
from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.providers.base import AIProvider

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_GEMINI_MODEL,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is not set. Configure it in your .env file."
            )
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    def _contents(self, messages: list[ChatMessage]) -> list[dict]:
        contents: list[dict] = []
        for m in messages:
            if m.role == ChatRole.SYSTEM:
                # Fold system into a user turn — Gemini has no separate system role here.
                role = "user"
                text = m.content
            elif m.role == ChatRole.ASSISTANT:
                role = "model"
                text = m.content
            else:
                role = "user"
                text = m.content
            parts: list[dict] = [{"text": text}]
            for image in m.images or []:
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": image.mime_type,
                            "data": image.data_base64,
                        }
                    }
                )
            contents.append({"role": role, "parts": parts})
        return contents

    def _url(self, stream: bool = False) -> str:
        action = "streamGenerateContent" if stream else "generateContent"
        return f"{_API_ROOT}/models/{self._model}:{action}"

    async def generate(self, messages: list[ChatMessage]) -> str:
        payload = {"contents": self._contents(messages)}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self._url(False), json=payload, headers={"x-goog-api-key": self._api_key})
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"Gemini request failed: {exc}") from exc
        if response.status_code == 401 or response.status_code == 403:
            raise ProviderConfigurationError("Gemini rejected the API key or access.")
        if response.status_code >= 400:
            raise ModelError(f"Gemini request failed ({response.status_code}).")
        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("Gemini returned an empty or malformed response.") from exc
        if not text:
            raise ModelError("Gemini returned an empty response.")
        return text

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        # Gemini streaming via SSE is optional; fall back to one-shot for honesty.
        text = await self.generate(messages)
        if text:
            yield text

    async def health_check(self) -> bool:
        try:
            url = f"{_API_ROOT}/models/{self._model}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers={"x-goog-api-key": self._api_key})
            return response.status_code < 400
        except Exception:  # noqa: BLE001
            return False
