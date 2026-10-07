"""Provider for a self-hosted / local model server (e.g. Ollama-compatible).
Talks to an HTTP endpoint configured via ``LOCAL_MODEL_URL``. This is an
interface/adapter for local inference servers; it does not bundle any model
weights or run inference in-process.
"""
from __future__ import annotations
import json
import time
from collections.abc import AsyncIterator
import httpx
from app.core.logging_config import get_logger
from app.models.chat import ChatMessage
from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.providers.base import AIProvider
from app.providers.http_pool import get_http_client
logger = get_logger("nexa.provider.local")
# Keep the weights resident between chats. Ollama's default is 5 minutes,
# which makes the next message pay a full model load before the first token.
_KEEP_ALIVE = "30m"


def _ollama_error_message(response: httpx.Response, model: str) -> str:
    return _ollama_error_message_from_bytes(response.content, response.status_code, model)


def _ollama_error_message_from_bytes(body: bytes, status_code: int, model: str) -> str:
    detail = ""
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
        if isinstance(data, dict):
            detail = str(data.get("error") or data.get("message") or "").strip()
    except Exception:  # noqa: BLE001
        detail = body.decode("utf-8", errors="replace").strip()[:400]
    if status_code == 402 or "not in the Free plan" in detail or "ollama.com/upgrade" in detail:
        return (
            f"Model '{model}' needs an Ollama Pro cloud plan. "
            "Install a free local model (e.g. `ollama pull llama3.2:3b`) "
            "and set LOCAL_MODEL_NAME to that model name."
        )
    if status_code == 404 or "not found" in detail.lower():
        return (
            f"Model '{model}' is not installed in Ollama. "
            f"Run `ollama pull {model}` or change LOCAL_MODEL_NAME."
        )
    if detail:
        return f"Ollama error ({status_code}) for '{model}': {detail}"
    return f"Ollama request failed with status {status_code} for model '{model}'."
class LocalProvider(AIProvider):
    """Provider that delegates chat completion to a local inference server."""
    name = "local"
    def __init__(
        self,
        base_url: str | None,
        model: str = "llama3",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url:
            raise ProviderConfigurationError(
                "LOCAL_MODEL_URL is not set. Configure it in your .env file."
            )
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
    @property
    def model_name(self) -> str:
        return self._model
    def _to_payload(self, messages: list[ChatMessage], stream: bool) -> dict:
        encoded_messages = []
        for m in messages:
            entry: dict = {"role": m.role.value, "content": m.content}
            if m.images:
                # Ollama's /api/chat accepts a per-message "images" array of
                # base64 strings for vision-capable models (e.g. llava).
                entry["images"] = [image.data_base64 for image in m.images]
            encoded_messages.append(entry)
        return {
            "model": self._model,
            "messages": encoded_messages,
            "stream": stream,
            "keep_alive": _KEEP_ALIVE,
            # Smaller context = faster prefill/TTFT. Do not cap num_predict —
            # that would artificially truncate long answers.
            "options": {
                "temperature": 0.4,
                "num_ctx": 2048,
            },
        }
    async def generate(self, messages: list[ChatMessage]) -> str:
        url = f"{self._base_url}/api/chat"
        started = time.perf_counter()
        logger.info("provider request start model=%s messages=%d stream=false", self._model, len(messages))
        try:
            client = get_http_client(self._timeout_seconds)
            response = await client.post(
                url,
                json=self._to_payload(messages, stream=False),
                timeout=self._timeout_seconds,
            )
            if response.status_code >= 400:
                raise ModelError(_ollama_error_message(response, self._model))
            data = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"Local model request failed: {exc}") from exc
        logger.info(
            "provider response done model=%s total_ms=%.1f",
            self._model,
            (time.perf_counter() - started) * 1000,
        )
        content = (
            data.get("message", {}).get("content")
            if isinstance(data, dict)
            else None
        )
        if not content:
            raise ModelError("Local model returned an empty response.")
        return content
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        url = f"{self._base_url}/api/chat"
        started = time.perf_counter()
        first_token_ms: float | None = None
        logger.info("provider request start model=%s messages=%d stream=true", self._model, len(messages))
        try:
            client = get_http_client(self._timeout_seconds)
            async with client.stream(
                "POST",
                url,
                json=self._to_payload(messages, stream=True),
                timeout=self._timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ModelError(
                        _ollama_error_message_from_bytes(body, response.status_code, self._model)
                    )
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue
                    content = chunk.get("message", {}).get("content")
                    if content:
                        if first_token_ms is None:
                            first_token_ms = (time.perf_counter() - started) * 1000
                            logger.info(
                                "provider first token model=%s ttft_ms=%.1f",
                                self._model,
                                first_token_ms,
                            )
                        yield content
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"Local model streaming request failed: {exc}") from exc
        logger.info(
            "provider stream done model=%s ttft_ms=%s total_ms=%.1f",
            self._model,
            f"{first_token_ms:.1f}" if first_token_ms is not None else "none",
            (time.perf_counter() - started) * 1000,
        )
    async def health_check(self) -> bool:
        try:
            client = get_http_client(5.0)
            response = await client.get(f"{self._base_url}/", timeout=5.0)
            return response.status_code < 500
        except Exception:  # noqa: BLE001
            return False
