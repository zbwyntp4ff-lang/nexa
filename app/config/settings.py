"""Application configuration.
All configuration is loaded from environment variables (optionally via a
``.env`` file). Secrets (API keys) must never be hard-coded and must never be
logged - see :mod:`app.core.logging_config` for the log redaction filter.
"""
from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
ProviderName = Literal[
    "mock", "openai", "anthropic", "gemini", "openrouter", "local", "ollama", "hexa", "nexa"
]
# Providers that are already implemented. ``ollama`` is the local server
# under its product name; ``local`` remains as the original alias.
SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "mock",
    "openai",
    "anthropic",
    "gemini",
    "openrouter",
    "local",
    "ollama",
    "hexa",
)
class Settings(BaseSettings):
    """Central application settings, populated from the environment."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    # --- Application ---------------------------------------------------
    app_name: str = Field(default="NEXA AI")
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    # persistent = durable disk (desktop / VPS / Railway+volume).
    # ephemeral = free-tier hosts without disk (e.g. Render Free) — data lost on restart.
    nexa_storage_mode: str = Field(default="persistent", alias="NEXA_STORAGE_MODE")
    # SQL store for server-side conversations (and future durable tables).
    # sqlite:///data/nexa.db (default) or postgresql://USER:PASS@HOST/DB
    database_url: str = Field(default="sqlite:///data/nexa.db", alias="DATABASE_URL")
    # sql = durable Memory via DATABASE_URL; json = legacy MEMORY_STORE_PATH file.
    memory_backend: str = Field(default="sql", alias="MEMORY_BACKEND")
    # API-wide rate limit (per IP / minute). 0 disables.
    api_rate_limit_per_minute: int = Field(default=120, alias="API_RATE_LIMIT_PER_MINUTE")
    # Free / smoke-test mode: tighter caps (does not invent token usage).
    free_tier_mode: bool = Field(default=False, alias="FREE_TIER_MODE")
    free_tier_daily_chat_cap: int = Field(default=50, alias="FREE_TIER_DAILY_CHAT_CAP")
    # Open public beta host: applies the same hard startup guards as durable
    # production (TOKENS_ENFORCE, no desktop tools, no mock, email verify, …).
    nexa_public_beta: bool = Field(default=False, alias="NEXA_PUBLIC_BETA")
    # Emergency stop for all model calls (ops kill switch).
    ai_kill_switch: bool = Field(default=False, alias="NEXA_AI_KILL_SWITCH")
    # Max concurrent /agent runs per authenticated user (0 = unlimited).
    agent_max_parallel_per_user: int = Field(
        default=2, alias="AGENT_MAX_PARALLEL_PER_USER"
    )
    # Registration abuse guard (IP).
    register_rate_limit_per_hour: int = Field(
        default=10, alias="REGISTER_RATE_LIMIT_PER_HOUR"
    )
    # --- Provider selection ---------------------------------------------
    ai_provider: str = Field(default="mock", alias="AI_PROVIDER")
    # --- OpenAI ----------------------------------------------------------
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    # --- Anthropic ---------------------------------------------------------
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-latest", alias="ANTHROPIC_MODEL"
    )
    # --- Google Gemini -----------------------------------------------------
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    # Alias accepted via env GOOGLE_API_KEY through property below if GEMINI unset.
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    # --- OpenRouter (OpenAI-compatible) ------------------------------------
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    # --- Local model -------------------------------------------------------
    local_model_url: str = Field(
        default="http://localhost:11434", alias="LOCAL_MODEL_URL"
    )
    local_model_name: str = Field(default="llama3.2:3b", alias="LOCAL_MODEL_NAME")
    # HEXA 4.5 inference server (Ollama-compatible HTTP API).
    hexa_model_url: str = Field(default="", alias="HEXA_MODEL_URL")
    hexa_model_name: str = Field(default="hexa-4.5", alias="HEXA_MODEL_NAME")
    # --- Model gateway (Part 7A) ------------------------------------------
    # Empty = pin the provider/model selected by AI_PROVIDER. "auto" lets
    # the selection policy choose an available model for the task.
    model_selection: str = Field(default="", alias="MODEL_SELECTION")
    allow_model_fallback: bool = Field(default=False, alias="ALLOW_MODEL_FALLBACK")
    # --- Request handling -------------------------------------------------
    max_message_length: int = Field(default=4000, alias="MAX_MESSAGE_LENGTH")
    request_timeout_seconds: float = Field(
        default=30.0, alias="REQUEST_TIMEOUT_SECONDS"
    )
    # --- Memory (Part 2) --------------------------------------------------
    memory_store_path: str = Field(
        default="data/memory_store.json", alias="MEMORY_STORE_PATH"
    )
    memory_search_limit: int = Field(default=10, alias="MEMORY_SEARCH_LIMIT")
    # --- Tools / filesystem sandbox (Part 2) ------------------------------
    agent_workspace_dir: str = Field(
        default="agent_workspace", alias="AGENT_WORKSPACE_DIR"
    )
    max_file_read_bytes: int = Field(
        default=1_000_000, alias="MAX_FILE_READ_BYTES"
    )
    # --- Plugin Hub (Part 14) ------------------------------------------------
    plugin_store_path: str = Field(
        default="data/plugin_store.json", alias="PLUGIN_STORE_PATH"
    )
    plugin_workspace_dir: str = Field(
        default="data/plugin_workspaces", alias="PLUGIN_WORKSPACE_DIR"
    )
    plugin_key_path: str = Field(default="data/plugin.key", alias="PLUGIN_KEY_PATH")
    plugin_timeout_seconds: float = Field(
        default=20.0, alias="PLUGIN_TIMEOUT_SECONDS"
    )
    plugin_max_file_bytes: int = Field(
        default=1_000_000, alias="PLUGIN_MAX_FILE_BYTES"
    )
    # --- Agent (Part 2) ----------------------------------------------------
    agent_max_steps: int = Field(default=10, alias="AGENT_MAX_STEPS")
    agent_timeout_seconds: float = Field(default=90.0, alias="AGENT_TIMEOUT_SECONDS")
    agent_error_limit: int = Field(default=3, alias="AGENT_ERROR_LIMIT")
    # --- Build Evaluation Engine V1 ---------------------------------------
    build_eval_pass_threshold: int = Field(default=70, alias="BUILD_EVAL_PASS_THRESHOLD")
    build_eval_max_improvement_attempts: int = Field(
        default=3, alias="BUILD_EVAL_MAX_IMPROVEMENT_ATTEMPTS"
    )
    # --- Web research (Part 3) ---------------------------------------------
    web_search_provider: str = Field(default="duckduckgo", alias="WEB_SEARCH_PROVIDER")
    search_api_url: str | None = Field(default=None, alias="SEARCH_API_URL")
    search_api_key: str | None = Field(default=None, alias="SEARCH_API_KEY")
    web_fetch_timeout_seconds: float = Field(
        default=10.0, alias="WEB_FETCH_TIMEOUT_SECONDS"
    )
    web_max_page_size_bytes: int = Field(
        default=2_000_000, alias="WEB_MAX_PAGE_SIZE_BYTES"
    )
    web_max_search_results: int = Field(default=5, alias="WEB_MAX_SEARCH_RESULTS")
    web_max_redirects: int = Field(default=3, alias="WEB_MAX_REDIRECTS")
    # --- Vision (Part 3) -----------------------------------------------------
    # none = honest not-configured (default). mock only for local tests.
    vision_provider: str = Field(default="none", alias="VISION_PROVIDER")
    openai_vision_model: str = Field(default="gpt-4o-mini", alias="OPENAI_VISION_MODEL")
    # --- Documents (Part 3) ---------------------------------------------------
    max_document_size_bytes: int = Field(
        default=10_000_000, alias="MAX_DOCUMENT_SIZE_BYTES"
    )
    # --- Attachments / multimodal input (Part 8) --------------------------
    max_attachment_size_bytes: int = Field(
        default=10_000_000, alias="MAX_ATTACHMENT_SIZE_BYTES"
    )
    max_attachments_per_message: int = Field(
        default=5, alias="MAX_ATTACHMENTS_PER_MESSAGE"
    )
    max_document_pages: int = Field(default=200, alias="MAX_DOCUMENT_PAGES")
    max_extracted_text_chars: int = Field(
        default=200_000, alias="MAX_EXTRACTED_TEXT_CHARS"
    )
    attachment_processing_timeout_seconds: float = Field(
        default=20.0, alias="ATTACHMENT_PROCESSING_TIMEOUT_SECONDS"
    )
    max_concurrent_attachment_jobs: int = Field(
        default=4, alias="MAX_CONCURRENT_ATTACHMENT_JOBS"
    )
    attachment_ttl_seconds: float = Field(
        default=3600.0, alias="ATTACHMENT_TTL_SECONDS"
    )
    attachment_context_max_chars: int = Field(
        default=6_000, alias="ATTACHMENT_CONTEXT_MAX_CHARS"
    )
    attachment_storage_dir: str = Field(
        default="data/attachments_tmp", alias="ATTACHMENT_STORAGE_DIR"
    )
    # --- Knowledge Base / RAG (Part 9) --------------------------------------
    knowledge_chunk_size_chars: int = Field(default=1_500, alias="KNOWLEDGE_CHUNK_SIZE_CHARS")
    knowledge_chunk_overlap_chars: int = Field(default=150, alias="KNOWLEDGE_CHUNK_OVERLAP_CHARS")
    knowledge_max_document_size_bytes: int = Field(
        default=10_000_000, alias="KNOWLEDGE_MAX_DOCUMENT_SIZE_BYTES"
    )
    knowledge_max_chunks_per_document: int = Field(
        default=500, alias="KNOWLEDGE_MAX_CHUNKS_PER_DOCUMENT"
    )
    knowledge_top_k: int = Field(default=5, alias="KNOWLEDGE_TOP_K")
    knowledge_similarity_threshold: float = Field(
        default=0.28, alias="KNOWLEDGE_SIMILARITY_THRESHOLD"
    )
    knowledge_max_context_chars: int = Field(
        default=6_000, alias="KNOWLEDGE_MAX_CONTEXT_CHARS"
    )
    knowledge_indexing_timeout_seconds: float = Field(
        default=20.0, alias="KNOWLEDGE_INDEXING_TIMEOUT_SECONDS"
    )
    knowledge_embedding_provider: str = Field(default="local", alias="KNOWLEDGE_EMBEDDING_PROVIDER")
    knowledge_embedding_model: str = Field(default="nomic-embed-text", alias="KNOWLEDGE_EMBEDDING_MODEL")
    knowledge_embedding_base_url: str = Field(default="http://127.0.0.1:11434", alias="KNOWLEDGE_EMBEDDING_BASE_URL")
    knowledge_embedding_timeout_seconds: float = Field(default=20.0, alias="KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS")
    knowledge_embedding_dimensions: int = Field(
        default=256, alias="KNOWLEDGE_EMBEDDING_DIMENSIONS"
    )
    knowledge_store_path: str = Field(
        default="data/knowledge_vectors.json", alias="KNOWLEDGE_STORE_PATH"
    )
    knowledge_documents_path: str = Field(
        default="data/knowledge_documents.json", alias="KNOWLEDGE_DOCUMENTS_PATH"
    )
    # --- Image generation (Part 3) --------------------------------------------
    image_provider: str = Field(default="none", alias="IMAGE_PROVIDER")
    openai_image_model: str = Field(default="dall-e-3", alias="OPENAI_IMAGE_MODEL")
    # --- Image-to-video (real providers only; no mock video) --------------------
    video_provider: str = Field(default="none", alias="VIDEO_PROVIDER")
    replicate_api_token: str | None = Field(default=None, alias="REPLICATE_API_TOKEN")
    replicate_i2v_model: str = Field(
        default="kwaivgi/kling-v1.6-standard", alias="REPLICATE_I2V_MODEL"
    )
    fal_key: str | None = Field(default=None, alias="FAL_KEY")
    fal_i2v_model: str = Field(
        default="fal-ai/minimax/video-01-live", alias="FAL_I2V_MODEL"
    )
    video_storage_dir: str = Field(default="data/videos", alias="VIDEO_STORAGE_DIR")
    video_timeout_seconds: float = Field(default=600.0, alias="VIDEO_TIMEOUT_SECONDS")
    # When true and a logged-in user is present, require plan feature image_to_video.
    video_require_entitlement: bool = Field(
        default=True, alias="VIDEO_REQUIRE_ENTITLEMENT"
    )
    # --- Voice (Part 3, interfaces only) --------------------------------------
    stt_provider: str = Field(default="none", alias="STT_PROVIDER")
    tts_provider: str = Field(default="none", alias="TTS_PROVIDER")
    # --- Auth / sessions ------------------------------------------------------
    auth_store_path: str = Field(default="data/auth_store.json", alias="AUTH_STORE_PATH")
    auth_session_cookie_name: str = Field(
        default="nexa_session", alias="AUTH_SESSION_COOKIE_NAME"
    )
    # Default 90 days; sliding renewal on activity keeps the session until logout.
    auth_session_ttl_seconds: int = Field(
        default=7_776_000, alias="AUTH_SESSION_TTL_SECONDS"
    )  # 14 days
    auth_code_ttl_seconds: int = Field(default=900, alias="AUTH_CODE_TTL_SECONDS")
    auth_code_resend_cooldown_seconds: int = Field(
        default=60, alias="AUTH_CODE_RESEND_COOLDOWN_SECONDS"
    )
    auth_code_max_attempts: int = Field(default=5, alias="AUTH_CODE_MAX_ATTEMPTS")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", alias="AUTH_COOKIE_SAMESITE")
    # Comma-separated emails that see the in-app Developer button.
    # Empty = nobody via allow-list; first verified account still becomes
    # owner when AUTH_BOOTSTRAP_FIRST_OWNER=true (default).
    auth_owner_emails_raw: str = Field(default="", alias="AUTH_OWNER_EMAILS")
    auth_bootstrap_first_owner: bool = Field(
        default=True, alias="AUTH_BOOTSTRAP_FIRST_OWNER"
    )
    # Multi-user by default: anyone can register. Set AUTH_SINGLE_USER=true for
    # a private desktop install (sign-up closes after the first account).
    auth_single_user: bool = Field(default=False, alias="AUTH_SINGLE_USER")
    auth_skip_email_verification: bool = Field(
        default=True, alias="AUTH_SKIP_EMAIL_VERIFICATION"
    )
    # Public origin for OAuth redirects + device/QR verification links.
    # Falls back to BILLING_PUBLIC_BASE_URL when empty.
    auth_public_base_url: str = Field(default="", alias="AUTH_PUBLIC_BASE_URL")
    # OAuth (optional — buttons show; disabled until credentials are set)
    oauth_google_client_id: str | None = Field(default=None, alias="OAUTH_GOOGLE_CLIENT_ID")
    oauth_google_client_secret: str | None = Field(
        default=None, alias="OAUTH_GOOGLE_CLIENT_SECRET"
    )
    oauth_github_client_id: str | None = Field(default=None, alias="OAUTH_GITHUB_CLIENT_ID")
    oauth_github_client_secret: str | None = Field(
        default=None, alias="OAUTH_GITHUB_CLIENT_SECRET"
    )
    oauth_apple_client_id: str | None = Field(default=None, alias="OAUTH_APPLE_CLIENT_ID")
    oauth_apple_client_secret: str | None = Field(
        default=None, alias="OAUTH_APPLE_CLIENT_SECRET"
    )
    auth_device_ttl_seconds: int = Field(default=600, alias="AUTH_DEVICE_TTL_SECONDS")
    auth_rp_id: str = Field(default="localhost", alias="AUTH_RP_ID")
    auth_rp_name: str = Field(default="NEXA", alias="AUTH_RP_NAME")
    oauth_credentials_dir: str = Field(default="data/oauth", alias="OAUTH_CREDENTIALS_DIR")
    auth_legal_dir: str = Field(default="data/legal", alias="AUTH_LEGAL_DIR")
    auth_legal_holder_name: str = Field(default="", alias="AUTH_LEGAL_HOLDER_NAME")
    auth_legal_holder_kind: str = Field(default="individual", alias="AUTH_LEGAL_HOLDER_KIND")
    auth_legal_contact: str = Field(default="", alias="AUTH_LEGAL_CONTACT")
    auth_legal_inn: str = Field(default="", alias="AUTH_LEGAL_INN")
    auth_api_public_url: str = Field(default="", alias="AUTH_API_PUBLIC_URL")
    # --- Billing / Stripe (production subscriptions) --------------------------
    # Use Stripe test keys for sandbox; live keys only in production.
    # Subscriptions activate ONLY after verified webhook events.
    billing_store_path: str = Field(
        default="data/billing_store.json", alias="BILLING_STORE_PATH"
    )
    # --- Internal AI tokens / credits -----------------------------------------
    token_store_path: str = Field(
        default="data/token_store.json", alias="TOKEN_STORE_PATH"
    )
    profile_store_path: str = Field(
        default="data/profile_store.json", alias="PROFILE_STORE_PATH"
    )
    # When true, AI routes require auth and charge tokens (production).
    # Tests/local API suites set TOKENS_ENFORCE=false via conftest.
    # Durable production startup refuses TOKENS_ENFORCE=false (see production_guards).
    tokens_enforce: bool = Field(default=True, alias="TOKENS_ENFORCE")
    # Autonomous workflows (/api/v1/workflows) are in-memory only until a durable
    # store ships. Public durable launch should set WORKFLOWS_ENABLED=false.
    workflows_enabled: bool = Field(default=True, alias="WORKFLOWS_ENABLED")
    token_default_balance: int = Field(default=100, alias="TOKEN_DEFAULT_BALANCE")
    token_default_daily_limit: int = Field(
        default=1_000, alias="TOKEN_DEFAULT_DAILY_LIMIT"
    )
    token_default_monthly_limit: int = Field(
        default=10_000, alias="TOKEN_DEFAULT_MONTHLY_LIMIT"
    )
    token_cost_chat: int = Field(default=1, alias="TOKEN_COST_CHAT")
    token_cost_agent: int = Field(default=5, alias="TOKEN_COST_AGENT")
    token_cost_image: int = Field(default=10, alias="TOKEN_COST_IMAGE")
    token_cost_default: int = Field(default=1, alias="TOKEN_COST_DEFAULT")
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str | None = Field(
        default=None, alias="STRIPE_PUBLISHABLE_KEY"
    )
    stripe_webhook_secret: str | None = Field(
        default=None, alias="STRIPE_WEBHOOK_SECRET"
    )
    # Optional pre-created Stripe Price IDs (preferred in production).
    # If empty, Checkout uses price_data from app/billing/plans.py amounts.
    stripe_price_starter_monthly: str | None = Field(
        default=None, alias="STRIPE_PRICE_STARTER_MONTHLY"
    )
    stripe_price_starter_yearly: str | None = Field(
        default=None, alias="STRIPE_PRICE_STARTER_YEARLY"
    )
    stripe_price_pro_monthly: str | None = Field(
        default=None, alias="STRIPE_PRICE_PRO_MONTHLY"
    )
    stripe_price_pro_yearly: str | None = Field(
        default=None, alias="STRIPE_PRICE_PRO_YEARLY"
    )
    stripe_price_business_monthly: str | None = Field(
        default=None, alias="STRIPE_PRICE_BUSINESS_MONTHLY"
    )
    stripe_price_business_yearly: str | None = Field(
        default=None, alias="STRIPE_PRICE_BUSINESS_YEARLY"
    )
    # Public site origin for Checkout success/cancel + Customer Portal return.
    billing_public_base_url: str = Field(
        default="http://localhost:4820", alias="BILLING_PUBLIC_BASE_URL"
    )
    billing_sales_email: str = Field(
        default="sales@nexa.ai", alias="BILLING_SALES_EMAIL"
    )
    # --- Email (auth transactional mail) --------------------------------------
    # EMAIL_PROVIDER: console (default, logs message) | smtp
    email_provider: str = Field(default="console", alias="EMAIL_PROVIDER")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")
    # --- CORS (Part 4, for the separate frontend app) --------------------------
    cors_allowed_origins_raw: str = Field(
        default=(
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:4820,http://127.0.0.1:4820,"
            # The packaged Electron app serves the frontend from a local
            # static server (frontend/electron/static-server.js) on this
            # fixed loopback port - without it listed here, every browser
            # fetch() from the renderer to this API fails CORS and the UI
            # silently sees empty/failed responses (e.g. an empty model list).
            "http://localhost:48420,http://127.0.0.1:48420"
        ),
        alias="CORS_ALLOWED_ORIGINS",
    )
    @field_validator("ai_provider")
    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        return value.strip().lower()
    @property
    def cors_allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins_raw.split(",") if origin.strip()]

    @property
    def resolved_gemini_api_key(self) -> str | None:
        """Prefer GEMINI_API_KEY; fall back to GOOGLE_API_KEY."""
        return (self.gemini_api_key or self.google_api_key or None)

    @property
    def auth_owner_emails(self) -> set[str]:
        return {
            e.strip().lower()
            for e in self.auth_owner_emails_raw.split(",")
            if e.strip()
        }
    def masked_dict(self) -> dict:
        """Return settings as a dict with secrets masked, safe for logging."""
        data = self.model_dump()
        for secret_key in (
            "openai_api_key",
            "anthropic_api_key",
            "gemini_api_key",
            "google_api_key",
            "openrouter_api_key",
            "smtp_password",
            "search_api_key",
            "stripe_secret_key",
            "stripe_webhook_secret",
            "replicate_api_token",
            "fal_key",
            "oauth_google_client_secret",
            "oauth_github_client_secret",
            "oauth_apple_client_secret",
        ):
            if data.get(secret_key):
                data[secret_key] = "***REDACTED***"
        return data
@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.
    Cached so the environment is only parsed once per process. Tests that
    need to override environment variables should call
    ``get_settings.cache_clear()`` first.
    """
    return Settings()
