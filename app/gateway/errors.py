"""Normalized provider errors for the Model Gateway.
Every provider failure is mapped to one of these codes before it reaches
NEXA Core, the agent, or the HTTP layer. Messages are passed through secret
redaction and never include API keys.
"""
from __future__ import annotations
import asyncio
from enum import Enum
from app.core.secrets import redact_secrets
from app.models.errors import NexaError, ProviderConfigurationError, ProviderTimeoutError
AUTHENTICATION_ERROR = "authentication_error"
RATE_LIMIT = "rate_limit"
TIMEOUT = "timeout"
PROVIDER_UNAVAILABLE = "provider_unavailable"
MODEL_UNAVAILABLE = "model_unavailable"
INVALID_REQUEST = "invalid_request"
UNKNOWN_ERROR = "unknown_error"
GATEWAY_ERROR_CODES: tuple[str, ...] = (
    AUTHENTICATION_ERROR,
    RATE_LIMIT,
    TIMEOUT,
    PROVIDER_UNAVAILABLE,
    MODEL_UNAVAILABLE,
    INVALID_REQUEST,
    UNKNOWN_ERROR,
)
# Transient failures may fall back to another provider when the user allowed
# it (or Auto is on). Critical failures are always shown as-is.
RETRYABLE_CODES: frozenset[str] = frozenset({RATE_LIMIT, TIMEOUT, PROVIDER_UNAVAILABLE})
_KEY_MISSING_MESSAGES = {
    "openai": (
        "OpenAI API key is not configured on the server. "
        "Set OPENAI_API_KEY in the backend environment."
    ),
    "anthropic": (
        "Anthropic API key is not configured on the server. "
        "Set ANTHROPIC_API_KEY in the backend environment."
    ),
    "gemini": (
        "Gemini API key is not configured on the server. "
        "Set GEMINI_API_KEY (or GOOGLE_API_KEY) in the backend environment."
    ),
    "openrouter": (
        "OpenRouter API key is not configured on the server. "
        "Set OPENROUTER_API_KEY in the backend environment."
    ),
}
class GatewayError(NexaError):
    """A provider failure with a stable ``code``."""
    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        safe = redact_secrets(message)
        super().__init__(safe)
        self.code = code if code in GATEWAY_ERROR_CODES else UNKNOWN_ERROR
        self.provider = provider
        self.model = model
        self.retryable = self.code in RETRYABLE_CODES
def missing_api_key_error(provider: str) -> GatewayError:
    message = _KEY_MISSING_MESSAGES.get(
        provider,
        f"{provider} is not configured on the server.",
    )
    return GatewayError(AUTHENTICATION_ERROR, message, provider=provider)
def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
    return None
def _walk(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__
def _safe_detail(exc: BaseException) -> str:
    text = redact_secrets(str(exc)).replace("\n", " ").strip()
    if len(text) > 180:
        text = text[:180] + "..."
    return text
def normalize_provider_error(
    exc: BaseException,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> GatewayError:
    """Map any provider exception to a :class:`GatewayError`."""
    if isinstance(exc, GatewayError):
        return exc
    for item in _walk(exc):
        if isinstance(item, ProviderConfigurationError):
            text = str(item).lower()
            if "not set" in text or "api_key" in text or "not configured" in text:
                return missing_api_key_error(provider or "provider")
            return GatewayError(
                PROVIDER_UNAVAILABLE,
                _safe_detail(item) or "Provider is not configured.",
                provider=provider,
                model=model,
            )
        if isinstance(item, (ProviderTimeoutError, TimeoutError, asyncio.TimeoutError)):
            return GatewayError(
                TIMEOUT,
                "The request to the AI provider timed out.",
                provider=provider,
                model=model,
            )
    status = None
    type_names = " ".join(type(item).__name__.lower() for item in _walk(exc))
    blob = type_names + " " + " ".join(_safe_detail(item).lower() for item in _walk(exc))
    for item in _walk(exc):
        status = _status_code(item)
        if status is not None:
            break
    if status in (401, 403) or "authentication" in blob or "permissiondenied" in type_names:
        return GatewayError(
            AUTHENTICATION_ERROR,
            "The AI provider rejected the credentials configured on the server.",
            provider=provider,
            model=model,
        )
    if status == 429 or "ratelimit" in type_names or "rate limit" in blob:
        return GatewayError(
            RATE_LIMIT,
            "The AI provider rate limit was reached. Try again shortly.",
            provider=provider,
            model=model,
        )
    if status == 408 or "timeout" in type_names or "timed out" in blob:
        return GatewayError(
            TIMEOUT,
            "The request to the AI provider timed out.",
            provider=provider,
            model=model,
        )
    if (
        status == 404
        or "notfound" in type_names
        or "model_not_found" in blob
        or "does not exist" in blob
        or "not available on this provider" in blob
        or "unavailable for free" in blob
    ):
        hint = (
            " Try openrouter/free or another :free model."
            if (provider or "") == "openrouter"
            else ""
        )
        return GatewayError(
            MODEL_UNAVAILABLE,
            f"The requested model is not available on this provider.{hint}",
            provider=provider,
            model=model,
        )
    if status in (400, 422) or "badrequest" in type_names or "invalid_request" in blob:
        return GatewayError(
            INVALID_REQUEST,
            "The AI provider rejected the request.",
            provider=provider,
            model=model,
        )
    if (
        status in (500, 502, 503, 504)
        or "connection" in type_names
        or "connecterror" in type_names
        or "unavailable" in blob
    ):
        return GatewayError(
            PROVIDER_UNAVAILABLE,
            "The AI provider is unavailable.",
            provider=provider,
            model=model,
        )
    return GatewayError(
        UNKNOWN_ERROR,
        "The AI provider failed to generate a response.",
        provider=provider,
        model=model,
    )
