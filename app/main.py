"""NEXA AI application entry point.
Run locally with:
    uvicorn app.main:app --reload --port 8420
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from app.api.routes import (
    agents,
    agent,
    attachments,
    auth,
    billing,
    beta,
    build,
    chat,
    conversations,
    health,
    image,
    knowledge,
    knowledge_core,
    learning,
    memory,
    model,
    models,
    observability,
    plugins,
    profile,
    projects,
    research,
    results,
    status,
    tokens,
    video,
    voice,
    workflow,
    workflows,
)
from app.attachments.manager import get_attachment_manager
from app.config.settings import get_settings
from app.core.logging_config import configure_logging, get_logger
from app.gateway.errors import GatewayError
from app.plugins.errors import (
    PluginConfirmationRequiredError,
    PluginError,
    PluginNotConnectedError,
    PluginNotFoundError,
    PluginPermissionDeniedError,
    PluginTimeoutError,
    PluginUnavailableError,
    PluginValidationError,
)
from app.agent.concurrency import AgentBusyError
from app.models.errors import (
    AgentTaskError,
    AttachmentNotFoundError,
    AttachmentProcessingTimeoutError,
    AttachmentTooLargeError,
    AttachmentValidationError,
    DocumentParsingError,
    DocumentTooLargeError,
    EmptyMessageError,
    FeatureDisabledError,
    InvalidURLError,
    KnowledgeDocumentNotFoundError,
    KnowledgeIndexingTimeoutError,
    KnowledgeSourceNotAllowedError,
    WorkflowCycleError,
    WorkflowInvalidTaskError,
    WorkflowLimitError,
    WorkflowNotFoundError,
    WorkflowSecurityError,
    WorkflowStateError,
    MemoryItemNotFoundError,
    MessageTooLongError,
    ModelCapabilityError,
    ModelError,
    NexaError,
    PageTooLargeError,
    PathTraversalError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    SearchError,
    SecretInMemoryError,
    SSRFProtectionError,
    ToolAlreadyRegisteredError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolPermissionError,
    ToolValidationError,
    TooManyAttachmentsError,
    TooManyConcurrentJobsError,
    UnknownProviderError,
    UnsupportedAttachmentFormatError,
    UnsupportedDocumentFormatError,
    WebFetchError,
    WebFetchTimeoutError,
)
from app.billing.errors import (
    BillingError,
    BillingNotConfiguredError,
    EntitlementDeniedError,
    PlanNotPurchasableError,
    RateLimitedError,
    UsageLimitExceededError,
    WebhookSignatureError,
)
from app.tokens.errors import (
    DailyTokenLimitError,
    InsufficientTokensError,
    InvalidTokenAmountError,
    MonthlyTokenLimitError,
    NegativeBalanceError,
    TokenAdminRequiredError,
    TokenError,
)
from app.auth.errors import (
    AccountDeleteConfirmError,
    AccountNotActiveError,
    AuthError,
    ConsentRequiredError,
    DeviceLoginError,
    DeviceLoginPendingError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidVerificationCodeError,
    OAuthStateInvalidError,
    PasskeyError,
    PasswordMismatchError,
    SessionInvalidError,
    UnauthorizedError,
    UsernameTakenError,
    ValidationAuthError,
    VerificationAttemptsExceededError,
    VerificationCodeExpiredError,
    VerificationResendCooldownError,
    WeakPasswordError,
    RegistrationClosedError,
)
from app.auth.oauth import OAuthExchangeError, OAuthNotConfiguredError
from app.models.status import ErrorResponse
settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("nexa.api")
_ATTACHMENT_CLEANUP_INTERVAL_SECONDS = 60.0
async def _attachment_cleanup_loop() -> None:
    """Periodically sweep expired temp attachments even without new requests."""
    manager = get_attachment_manager()
    from app.core.paths import resolve_under_project_root
    from app.video_generation.service import get_video_job_store

    video_store = get_video_job_store()
    video_storage_dir = resolve_under_project_root(settings.video_storage_dir)
    while True:
        await asyncio.sleep(_ATTACHMENT_CLEANUP_INTERVAL_SECONDS)
        try:
            manager.cleanup_expired()
            video_store.cleanup_expired(video_storage_dir)
        except Exception:  # noqa: BLE001 - a cleanup hiccup must never crash the app
            logger.exception("attachment cleanup sweep failed")
async def _warm_inference() -> None:
    """Prefetch Ollama tags and keep the active local model resident.

    Runs in the background so startup stays fast; first user chat then skips
    cold model load + tags round-trip.
    """
    try:
        from app.api.deps import get_nexa_core
        from app.models.chat import ChatMessage, ChatRole

        core = get_nexa_core()
        if core.gateway is None:
            return
        await core.gateway.refresh_ollama(force=True)
        card = core.gateway.active_card()
        if card.provider not in ("ollama", "local") or card.availability != "available":
            return
        provider = core.gateway._open(card)  # noqa: SLF001 - warm path shares gateway open
        # Tiny completion just to load weights into VRAM/RAM (keep_alive on provider).
        await asyncio.wait_for(
            provider.generate([ChatMessage(role=ChatRole.USER, content="ok")]),
            timeout=60.0,
        )
        logger.info("warm inference ready model=%s", card.model_id)
    except Exception:  # noqa: BLE001
        logger.info("warm inference skipped")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from app.config.production_guards import (
        assert_durable_production,
        is_durable_production,
        is_public_cloud,
    )

    # Durable production and NEXA_PUBLIC_BETA share the same hard fail path.
    assert_durable_production(settings)
    try:
        from app.conversations.store import get_conversation_store
        from app.db.engine import get_database
        from app.memory.manager import get_memory_manager

        get_database.cache_clear()
        get_conversation_store.cache_clear()
        get_memory_manager.cache_clear()
        get_database().migrate()
        get_conversation_store()
        get_memory_manager()
        logger.info("database migrate ok")
    except Exception:  # noqa: BLE001
        logger.exception("database migrate failed")
        if is_durable_production(settings) or is_public_cloud(settings):
            raise
    task = asyncio.create_task(_attachment_cleanup_loop())
    warm = asyncio.create_task(_warm_inference())
    try:
        yield
    finally:
        warm.cancel()
        task.cancel()


_disable_docs = (settings.environment or "").strip().lower() == "production"
app = FastAPI(
    title="NEXA AI",
    description="Cloud-first multi-user AI platform (HEXARI).",
    version="2.0.0-cloud",
    lifespan=_lifespan,
    docs_url=None if _disable_docs else "/docs",
    redoc_url=None if _disable_docs else "/redoc",
    openapi_url=None if _disable_docs else "/openapi.json",
)
# Allows the NEXA frontend (a separate app/process, see frontend/) to call
# this API from the browser during local development. No credentials or API
# keys ever cross this boundary - the frontend only ever talks to this
# backend, never directly to OpenAI/Anthropic/etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from app.web.csrf import CookieCSRFMiddleware
from app.web.rate_limit import ApiRateLimitMiddleware

app.add_middleware(
    ApiRateLimitMiddleware,
    max_calls=settings.api_rate_limit_per_minute,
    window_seconds=60.0,
)

app.add_middleware(CookieCSRFMiddleware)
from app.auth.device_page import DEVICE_PAGE_HTML

@app.get("/auth/device", include_in_schema=False)
async def device_login_page() -> HTMLResponse:
    """Phone-facing QR landing page. Must be reachable on the LAN (not localhost)."""
    return HTMLResponse(DEVICE_PAGE_HTML)

app.include_router(health.router)
app.include_router(status.router)
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(profile.router)
app.include_router(billing.router)
app.include_router(beta.router)
app.include_router(tokens.router)
app.include_router(model.router)
app.include_router(models.router)
app.include_router(chat.router)
app.include_router(knowledge_core.router)
app.include_router(learning.router)
app.include_router(conversations.router)
app.include_router(memory.router)
app.include_router(agent.router)
app.include_router(results.router)
app.include_router(projects.router)
app.include_router(observability.router)
app.include_router(build.router)
app.include_router(research.router)
app.include_router(image.router)
app.include_router(video.router)
app.include_router(attachments.router)
app.include_router(knowledge.router)
app.include_router(voice.router)
app.include_router(workflow.router)
app.include_router(workflows.router)
app.include_router(plugins.router)
# --- Error handling ---------------------------------------------------------
# Domain errors are mapped to stable HTTP status codes and a safe, generic
# error envelope. Internal details (stack traces, raw exception text from
# third-party SDKs) are logged server-side only, never returned to clients.
_ERROR_STATUS_MAP: dict[type[NexaError], int] = {
    EmptyMessageError: 400,
    MessageTooLongError: 400,
    UnknownProviderError: 400,
    ProviderConfigurationError: 503,
    ProviderTimeoutError: 504,
    ModelError: 502,
    # --- Memory (Part 2) ---
    MemoryItemNotFoundError: 404,
    SecretInMemoryError: 400,
    # --- Tools (Part 2) ---
    ToolNotFoundError: 404,
    ToolAlreadyRegisteredError: 409,
    ToolPermissionError: 403,
    ToolValidationError: 400,
    ToolExecutionError: 502,
    PathTraversalError: 400,
    # --- Agent (Part 2) ---
    AgentTaskError: 400,
    AgentBusyError: 429,
    # --- Web research (Part 3) ---
    InvalidURLError: 400,
    SSRFProtectionError: 400,
    PageTooLargeError: 413,
    WebFetchTimeoutError: 504,
    WebFetchError: 502,
    SearchError: 502,
    # --- Documents (Part 3) ---
    UnsupportedDocumentFormatError: 400,
    DocumentTooLargeError: 400,
    DocumentParsingError: 422,
    # --- Attachments / multimodal input (Part 8) ---
    AttachmentNotFoundError: 404,
    AttachmentValidationError: 400,
    AttachmentTooLargeError: 413,
    UnsupportedAttachmentFormatError: 400,
    TooManyAttachmentsError: 400,
    AttachmentProcessingTimeoutError: 504,
    TooManyConcurrentJobsError: 429,
    ModelCapabilityError: 400,
    # --- Knowledge Base / RAG (Part 9) ---
    KnowledgeDocumentNotFoundError: 404,
    KnowledgeSourceNotAllowedError: 403,
    KnowledgeIndexingTimeoutError: 504,
    # --- Autonomous Workflows (Part 10) ---
    WorkflowNotFoundError: 404,
    WorkflowStateError: 409,
    WorkflowInvalidTaskError: 400,
    WorkflowCycleError: 400,
    WorkflowLimitError: 400,
    WorkflowSecurityError: 403,
    FeatureDisabledError: 503,
    # --- Auth ---
    EmailAlreadyRegisteredError: 409,
    UsernameTakenError: 409,
    InvalidCredentialsError: 401,
    EmailNotVerifiedError: 403,
    AccountNotActiveError: 403,
    ConsentRequiredError: 400,
    PasswordMismatchError: 400,
    WeakPasswordError: 400,
    InvalidVerificationCodeError: 400,
    VerificationCodeExpiredError: 400,
    VerificationAttemptsExceededError: 429,
    VerificationResendCooldownError: 429,
    UnauthorizedError: 401,
    SessionInvalidError: 401,
    ValidationAuthError: 400,
    RegistrationClosedError: 403,
    OAuthStateInvalidError: 400,
    OAuthNotConfiguredError: 503,
    OAuthExchangeError: 502,
    DeviceLoginPendingError: 428,
    DeviceLoginError: 400,
    PasskeyError: 401,
    AccountDeleteConfirmError: 400,
    AuthError: 400,
    # --- Billing ---
    BillingNotConfiguredError: 503,
    PlanNotPurchasableError: 400,
    EntitlementDeniedError: 403,
    UsageLimitExceededError: 402,
    WebhookSignatureError: 400,
    RateLimitedError: 429,
    BillingError: 400,
    # --- Tokens / credits ---
    InsufficientTokensError: 402,
    DailyTokenLimitError: 402,
    MonthlyTokenLimitError: 402,
    TokenAdminRequiredError: 403,
    InvalidTokenAmountError: 400,
    NegativeBalanceError: 500,
    TokenError: 400,
    # --- Plugin Hub (Part 14) ---
    PluginNotFoundError: 404,
    PluginNotConnectedError: 409,
    PluginPermissionDeniedError: 403,
    PluginConfirmationRequiredError: 400,
    PluginUnavailableError: 503,
    PluginTimeoutError: 504,
    PluginValidationError: 400,
    PluginError: 400,
}
_GATEWAY_STATUS = {
    "authentication_error": 503,
    "rate_limit": 429,
    "timeout": 504,
    "provider_unavailable": 503,
    "model_unavailable": 404,
    "invalid_request": 400,
    "unknown_error": 502,
}
def _error_code(exc: NexaError) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    return exc.__class__.__name__


@app.exception_handler(NexaError)
async def nexa_error_handler(request: Request, exc: NexaError) -> JSONResponse:
    if isinstance(exc, GatewayError):
        status_code = _GATEWAY_STATUS.get(exc.code, 502)
    else:
        status_code = 500
        for exc_type, code in _ERROR_STATUS_MAP.items():
            if isinstance(exc, exc_type):
                status_code = code
                break
    if status_code >= 500:
        logger.error("unhandled domain error: %s: %s", _error_code(exc), exc.message)
    else:
        logger.warning("client error: %s: %s", _error_code(exc), exc.message)
    body: dict = ErrorResponse(error=_error_code(exc), message=exc.message).model_dump()
    if isinstance(exc, VerificationResendCooldownError):
        body["retry_after_seconds"] = exc.retry_after_seconds
    return JSONResponse(status_code=status_code, content=body)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred. Please try again later.",
        ).model_dump(),
    )
