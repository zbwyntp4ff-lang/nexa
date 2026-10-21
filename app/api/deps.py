"""FastAPI dependency wiring.
Builds a fresh :class:`NexaCore` (with a fresh provider) per settings state.
The provider/core pair is cached per-process via ``lru_cache`` for
performance, but tests can call :func:`get_nexa_core.cache_clear` after
mutating environment variables to force a rebuild.
"""
from __future__ import annotations
from functools import lru_cache

from app.agent.agent import Agent
from app.agent.executor import Executor
from app.agent.planner import RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.attachments.manager import get_attachment_manager
from app.auth.email import build_email_service
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.config.settings import get_settings
from app.core.nexa_core import NexaCore
from app.knowledge.knowledge_base import get_knowledge_base
from app.memory.manager import MemoryManager, get_memory_manager
from app.orchestrator.orchestrator import Orchestrator
from app.workflows.engine import WorkflowEngine
from app.gateway.gateway import build_model_gateway
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.factory import ImageGenerationProviderFactory
from app.providers.factory import ProviderFactory
from app.tools.registry import get_default_tool_registry


@lru_cache
def get_auth_store() -> AuthStore:
    return AuthStore(get_settings().auth_store_path)


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    public_base = (settings.auth_public_base_url or settings.billing_public_base_url or "").rstrip(
        "/"
    ) or "http://localhost:4820"
    return AuthService(
        get_auth_store(),
        build_email_service(settings),
        code_ttl_seconds=settings.auth_code_ttl_seconds,
        resend_cooldown_seconds=settings.auth_code_resend_cooldown_seconds,
        max_verify_attempts=settings.auth_code_max_attempts,
        session_ttl_seconds=settings.auth_session_ttl_seconds,
        app_name=settings.app_name,
        owner_emails=settings.auth_owner_emails,
        bootstrap_first_owner=settings.auth_bootstrap_first_owner,
        single_user=settings.auth_single_user,
        skip_email_verification=settings.auth_skip_email_verification,
        public_base_url=public_base,
        device_ttl_seconds=settings.auth_device_ttl_seconds,
        rp_id=settings.auth_rp_id,
        rp_name=settings.auth_rp_name,
        oauth_settings=settings,
        api_public_url=settings.auth_api_public_url,
    )
@lru_cache
def get_nexa_core() -> NexaCore:
    settings = get_settings()
    provider = ProviderFactory.create(settings)
    gateway = build_model_gateway(settings)
    return NexaCore(
        provider=provider,
        settings=settings,
        gateway=gateway,
        attachments=get_attachment_manager(),
        knowledge_base=get_knowledge_base(),
    )
def get_memory_manager_dep() -> MemoryManager:
    return get_memory_manager()
@lru_cache
def get_agent() -> Agent:
    """Build the default Agent (Part 2 planner/tools) - used by ``POST /api/v1/agent``."""
    settings = get_settings()
    registry = get_default_tool_registry()
    return Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        max_steps=settings.agent_max_steps,
        timeout_seconds=settings.agent_timeout_seconds,
        error_limit=settings.agent_error_limit,
        model_gateway=get_nexa_core().gateway,
    )
@lru_cache
def get_orchestrator() -> Orchestrator:
    """Build the default Orchestrator (Part 7) - used by ``POST /api/v1/workflow``."""
    registry = get_default_tool_registry()
    return Orchestrator(
        registry=registry,
        max_subtasks=8,
        timeout_seconds=120.0,
        step_timeout_seconds=30.0,
        model_gateway=get_nexa_core().gateway,
        attachment_manager=get_attachment_manager(),
    )
@lru_cache
def get_image_generation_provider() -> ImageGenerationProvider:
    """Image generation backend for Create mode (Part 3 interface, wired here).

    Defaults to :class:`app.image_generation.not_configured.NotConfiguredImageGenerationProvider`
    unless ``IMAGE_PROVIDER=openai`` and ``OPENAI_API_KEY`` are both set.
    """
    return ImageGenerationProviderFactory.create(get_settings())


@lru_cache
def get_image_to_video_service():
    from app.video_generation.factory import ImageToVideoProviderFactory
    from app.video_generation.service import ImageToVideoService

    settings = get_settings()
    return ImageToVideoService(
        settings=settings,
        provider=ImageToVideoProviderFactory.create(settings),
        attachments=get_attachment_manager(),
        entitlements=get_entitlement_service(),
    )


@lru_cache
def get_billing_store():
    from app.billing.store import BillingStore

    return BillingStore(get_settings().billing_store_path)


@lru_cache
def get_token_store():
    from app.tokens.store import TokenStore

    return TokenStore(get_settings().token_store_path)


@lru_cache
def get_token_service():
    from app.tokens.service import TokenService

    settings = get_settings()
    daily = settings.token_default_daily_limit
    monthly = settings.token_default_monthly_limit
    balance = settings.token_default_balance
    if settings.free_tier_mode:
        daily = min(daily, settings.free_tier_daily_chat_cap)
        monthly = min(monthly, max(settings.free_tier_daily_chat_cap * 30, 1))
        balance = min(balance, settings.free_tier_daily_chat_cap)
    return TokenService(
        get_token_store(),
        default_balance=balance,
        default_daily_limit=daily,
        default_monthly_limit=monthly,
        cost_chat=settings.token_cost_chat,
        cost_agent=settings.token_cost_agent,
        cost_image=settings.token_cost_image,
        cost_default=settings.token_cost_default,
    )


@lru_cache
def get_profile_store():
    from app.profile.store import ProfileStore

    return ProfileStore(get_settings().profile_store_path)


@lru_cache
def get_profile_service():
    from app.profile.service import ProfileService

    return ProfileService(get_profile_store())


@lru_cache
def get_entitlement_service():
    from app.billing.entitlements import EntitlementService

    return EntitlementService(get_billing_store())


@lru_cache
def get_billing_service():
    from app.billing.service import BillingService
    from app.billing.stripe_provider import StripeBillingProvider

    settings = get_settings()
    store = get_billing_store()
    return BillingService(
        store=store,
        provider=StripeBillingProvider(settings),
        entitlements=get_entitlement_service(),
        settings=settings,
    )


@lru_cache
def get_workflow_engine() -> WorkflowEngine:
    """Persistent autonomous workflows (Part 10). Separate from ``POST /api/v1/workflow``."""
    return WorkflowEngine(
        registry=get_default_tool_registry(),
        knowledge_base=get_knowledge_base(),
        model_gateway=get_nexa_core().gateway,
    )


def get_plugin_manager_dep():
    """Plugin Hub manager (Part 14). Cached inside ``app.plugins.manager``."""
    from app.plugins.manager import get_plugin_manager

    return get_plugin_manager()
