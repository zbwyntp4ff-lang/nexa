"""Shared pytest fixtures.
Ensures each test gets a clean settings/provider cache and does not leak
environment variables (or real API keys) between tests. No test in this
suite ever performs a real network call to an external AI provider.
"""
from __future__ import annotations
import os
import pytest
from app.api.deps import get_nexa_core, get_token_service, get_token_store
from app.config.settings import get_settings
from app.plugins.manager import get_plugin_manager
from app.tools.registry import get_default_tool_registry


def pytest_collection_modifyitems(config, items):
    """Keep marked network tests out of default CI runs unless opted in."""
    if os.environ.get("RUN_NETWORK_TESTS") == "1":
        return
    skip_net = pytest.mark.skip(reason="network test (set RUN_NETWORK_TESTS=1)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_net)


_ENV_KEYS = (
    "AI_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "LOCAL_MODEL_URL",
    "LOCAL_MODEL_NAME",
    "MAX_MESSAGE_LENGTH",
    "REQUEST_TIMEOUT_SECONDS",
    "TOKENS_ENFORCE",
    "TOKEN_STORE_PATH",
    "PLUGIN_STORE_PATH",
    "PLUGIN_KEY_PATH",
    "PLUGIN_WORKSPACE_DIR",
    "DATABASE_URL",
    "MEMORY_BACKEND",
    "API_RATE_LIMIT_PER_MINUTE",
)
@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path_factory):
    """Reset cached settings/core and restore environment after each test."""
    from app.auth.rate_limit import reset_auth_rate_limiters
    from app.conversations.store import get_conversation_store
    from app.db.engine import get_database
    from app.memory.manager import get_memory_manager
    from app.web.rate_limit import reset_api_rate_limiter

    original = {key: os.environ.get(key) for key in _ENV_KEYS}
    # Keep legacy chat/API tests unauthenticated unless a test opts in.
    os.environ.setdefault("TOKENS_ENFORCE", "false")
    # Force-disable API rate limit for the suite (middleware reads settings live).
    os.environ["API_RATE_LIMIT_PER_MINUTE"] = "0"
    os.environ.setdefault("MEMORY_BACKEND", "sql")
    token_path = tmp_path_factory.mktemp("tokens") / "token_store.json"
    os.environ["TOKEN_STORE_PATH"] = str(token_path)
    plugin_dir = tmp_path_factory.mktemp("plugins")
    os.environ["PLUGIN_STORE_PATH"] = str(plugin_dir / "plugin_store.json")
    os.environ["PLUGIN_KEY_PATH"] = str(plugin_dir / "plugin.key")
    os.environ["PLUGIN_WORKSPACE_DIR"] = str(plugin_dir / "ws")
    db_path = tmp_path_factory.mktemp("db") / "nexa.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
    get_token_store.cache_clear()
    get_token_service.cache_clear()
    get_plugin_manager.cache_clear()
    get_default_tool_registry.cache_clear()
    get_conversation_store.cache_clear()
    get_database.cache_clear()
    get_memory_manager.cache_clear()
    reset_auth_rate_limiters()
    reset_api_rate_limiter()
    # Tests register/login many users from one IP — raise auth caps for the suite.
    from app.auth.rate_limit import (
        login_account_limiter,
        login_ip_limiter,
        register_ip_limiter,
    )

    register_ip_limiter.configure(max_calls=10_000, window_seconds=3600.0)
    login_ip_limiter.configure(max_calls=10_000, window_seconds=60.0)
    login_account_limiter.configure(max_calls=10_000, window_seconds=60.0)
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
    get_token_store.cache_clear()
    get_token_service.cache_clear()
    get_plugin_manager.cache_clear()
    get_default_tool_registry.cache_clear()
    get_conversation_store.cache_clear()
    get_database.cache_clear()
    get_memory_manager.cache_clear()
    reset_auth_rate_limiters()
    reset_api_rate_limiter()
    register_ip_limiter.configure(max_calls=10, window_seconds=3600.0)
    login_ip_limiter.configure(max_calls=20, window_seconds=60.0)
    login_account_limiter.configure(max_calls=10, window_seconds=60.0)
