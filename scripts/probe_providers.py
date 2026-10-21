"""Probe configured providers without printing secrets."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from app.config.settings import get_settings

get_settings.cache_clear()
s = get_settings()
print("ai_provider=", s.ai_provider)
print("openai_model=", s.openai_model)
print("openrouter_model=", s.openrouter_model)
print("anthropic_model=", s.anthropic_model)
print("gemini_model=", s.gemini_model)
print("local_model_url=", s.local_model_url)
print("local_model_name=", s.local_model_name)
print("environment=", s.environment)
print("openai_key_set=", bool(s.openai_api_key))
print("openrouter_key_set=", bool(s.openrouter_api_key))
print("anthropic_key_set=", bool(s.anthropic_api_key))
print("gemini_key_set=", bool(s.resolved_gemini_api_key))
print("dotenv_exists=", Path(".env").is_file())
print("env_AI_PROVIDER=", "SET" if os.environ.get("AI_PROVIDER") else "UNSET")
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
        body = r.read()
        print("ollama_status=", r.status, "bytes=", len(body))
except Exception as exc:  # noqa: BLE001
    print("ollama=", type(exc).__name__, str(exc)[:100])
