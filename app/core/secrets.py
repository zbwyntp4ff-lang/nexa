"""Shared secret-detection utilities.
Used by both the logging subsystem (:mod:`app.core.logging_config`) and the
memory subsystem (:mod:`app.memory`) so that API keys, passwords and other
secrets are consistently redacted from logs and refused from persistent
storage.
"""
from __future__ import annotations
import re
SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(
        r"""(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret)\s*[:=]\s*["']?[^\s,;}"']+"""
    ),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    ),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),  # Anthropic-style keys (checked first: more specific)
    re.compile(r"sk_live_[A-Za-z0-9]{10,}"),  # Stripe live secret
    re.compile(r"sk_test_[A-Za-z0-9]{10,}"),  # Stripe test secret
    re.compile(r"whsec_[A-Za-z0-9]{10,}"),  # Stripe webhook secret
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),  # OpenAI / OpenRouter-style keys
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),  # Google / Gemini API keys
    re.compile(r"r8_[A-Za-z0-9]{10,}"),  # Replicate
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),  # GitHub personal access token
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),  # Fine-grained GitHub PAT
    re.compile(r"gho_[A-Za-z0-9]{20,}"),  # GitHub OAuth access token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]
# Field/key names that indicate the *value* should never be persisted or
# logged, regardless of its shape.
SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "openai_api_key",
        "anthropic_api_key",
        "gemini_api_key",
        "google_api_key",
        "openrouter_api_key",
        "password",
        "passwd",
        "secret",
        "secret_key",
        "access_token",
        "auth_token",
        "authorization",
        "token",
        "private_key",
        "github_token",
        "github_pat",
    }
)
REDACTED = "***REDACTED***"
def redact_secrets(text: str) -> str:
    """Replace any secret-shaped substrings in ``text`` with a redaction marker."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text
def contains_secret(text: str) -> bool:
    """Return ``True`` if ``text`` contains anything that looks like a secret."""
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)
def is_secret_field_name(name: str) -> bool:
    """Return ``True`` if a field/key name suggests its value is a secret."""
    return name.strip().lower().replace("-", "_") in SECRET_FIELD_NAMES
