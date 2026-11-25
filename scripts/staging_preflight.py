#!/usr/bin/env python3
"""Validate staging/public-beta Settings without printing secrets.

Usage (from repo root, with env already exported or a dotenv file loaded by
the platform — this script does not write env files):

  python scripts/staging_preflight.py

Exit 0 = production_guards accept the current process environment.
Exit 1 = problems listed (secret values never printed).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _present(name: str) -> str:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return "UNSET"
    if any(
        x in name.upper()
        for x in ("KEY", "PASSWORD", "SECRET", "TOKEN", "CREDENTIAL")
    ):
        return "SET"
    return raw


def main() -> int:
    from app.config.production_guards import validate_production_settings
    from app.config.settings import Settings, get_settings

    get_settings.cache_clear()
    # Prefer process env only — do not auto-load developer .env for this check.
    settings = Settings(_env_file=None)
    problems = validate_production_settings(settings)

    checklist = [
        "NEXA_PUBLIC_BETA",
        "ENVIRONMENT",
        "NEXA_STORAGE_MODE",
        "TOKENS_ENFORCE",
        "GUEST_QUOTA_HASH_KEY",
        "TRUSTED_EDGE_RATE_LIMIT_ENABLED",
        "API_RATE_LIMIT_PER_MINUTE",
        "REGISTER_RATE_LIMIT_PER_HOUR",
        "AUTH_SKIP_EMAIL_VERIFICATION",
        "AUTH_COOKIE_SECURE",
        "AUTH_SINGLE_USER",
        "EMAIL_PROVIDER",
        "SMTP_HOST",
        "EMAIL_FROM",
        "AI_PROVIDER",
        "OPENROUTER_MODEL",
        "OPENAI_MODEL",
        "ANTHROPIC_MODEL",
        "GEMINI_MODEL",
        "AUTH_PUBLIC_BASE_URL",
        "CORS_ALLOWED_ORIGINS",
        "MEMORY_BACKEND",
        "DATABASE_URL",
        "WORKFLOWS_ENABLED",
        "WEB_CONCURRENCY",
        "NEXA_LOCAL_DESKTOP",
        "NEXA_ELECTRON_ALLOW_LAN_BIND",
        "NEXA_ALLOW_PACKAGED_DEVTOOLS",
        "NEXA_AI_KILL_SWITCH",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "SMTP_PASSWORD",
    ]
    print("=== staging preflight (redacted) ===")
    for name in checklist:
        print(f"{name}={_present(name)}")

    if problems:
        print("=== GUARD FAILURES ===")
        for p in problems:
            print(f"- {p}")
        return 1

    print("=== OK: production_guards accept this environment ===")
    if not (
        (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
        or (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        or (os.environ.get("GEMINI_API_KEY") or "").strip()
    ):
        print(
            "NOTE: no cloud AI key detected in env — chat will fail until one is set."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
