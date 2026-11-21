"""Hard checks for durable public production and open public beta hosts.



Applied when:

- ``ENVIRONMENT=production`` and ``NEXA_STORAGE_MODE=persistent``, or

- ``NEXA_PUBLIC_BETA=true`` (explicit open-beta cloud profile).



Render Free / ephemeral smoke stays ``ephemeral`` and only logs warnings

unless ``NEXA_PUBLIC_BETA=true``.

"""

from __future__ import annotations



import os



from app.config.settings import Settings

from app.core.logging_config import get_logger



logger = get_logger("nexa.production")





def _flag_on(name: str) -> bool:

    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}





class ProductionConfigError(RuntimeError):

    """Raised when durable production / open-beta settings are unsafe."""





def is_durable_production(settings: Settings) -> bool:

    env = (settings.environment or "").strip().lower()

    mode = (settings.nexa_storage_mode or "").strip().lower()

    return env == "production" and mode == "persistent"





def is_public_cloud(settings: Settings) -> bool:

    """True when this process must enforce the public multi-user safety profile."""

    if bool(getattr(settings, "nexa_public_beta", False)):

        return True

    return is_durable_production(settings)





def validate_production_settings(settings: Settings) -> list[str]:

    """Return human-readable problems. Empty = OK for this mode."""

    problems: list[str] = []

    env = (settings.environment or "").strip().lower()

    mode = (settings.nexa_storage_mode or "").strip().lower()

    public_beta = bool(getattr(settings, "nexa_public_beta", False))



    if public_beta:

        return _public_cloud_problems(settings, label="open public beta")



    if env != "production":

        return problems



    if mode == "ephemeral":

        logger.warning(

            "ENVIRONMENT=production with NEXA_STORAGE_MODE=ephemeral — "

            "data will not survive restarts; not a public durable release"

        )

        if not settings.tokens_enforce:

            logger.warning(

                "TOKENS_ENFORCE=false under ENVIRONMENT=production (ephemeral): "

                "Results ACL and auth lockdown are disabled — desktop/pytest only"

            )

        return problems



    return _public_cloud_problems(settings, label="durable production")





def _public_cloud_problems(settings: Settings, *, label: str) -> list[str]:

    problems: list[str] = []

    if bool(getattr(settings, "nexa_public_beta", False)):
        quota_key = (getattr(settings, "guest_quota_hash_key", None) or "").strip()
        if len(quota_key) < 32:
            problems.append("GUEST_QUOTA_HASH_KEY must be set to at least 32 random characters for public beta")

    if not settings.trusted_edge_rate_limit_enabled:
        problems.append(
            "TRUSTED_EDGE_RATE_LIMIT_ENABLED must be true only after a trusted CDN/WAF "
            "or reverse proxy enforces distributed rate limits"
        )
    if settings.api_rate_limit_per_minute <= 0:
        problems.append("API_RATE_LIMIT_PER_MINUTE must be greater than zero")
    if settings.register_rate_limit_per_hour <= 0:
        problems.append("REGISTER_RATE_LIMIT_PER_HOUR must be greater than zero")

    if not settings.tokens_enforce:

        problems.append(

            f"TOKENS_ENFORCE must be true for {label} "

            "(anonymous Results/Build access is unsafe)"

        )

    if settings.auth_skip_email_verification:

        problems.append(

            "AUTH_SKIP_EMAIL_VERIFICATION must be false "

            "(configure SMTP / EMAIL_PROVIDER=smtp)"

        )

    if not settings.auth_cookie_secure:

        problems.append("AUTH_COOKIE_SECURE must be true behind HTTPS")

    if settings.auth_single_user:

        problems.append(

            "AUTH_SINGLE_USER=true blocks open self-registration — "

            f"must be false for {label}"

        )

    provider = (settings.ai_provider or "").strip().lower()

    if provider == "mock":

        problems.append(f"AI_PROVIDER=mock is not allowed for {label}")

    # Unverified free router routes are not safe defaults for paying/open users.

    or_model = (getattr(settings, "openrouter_model", None) or "").strip().lower()

    if provider == "openrouter" and (

        or_model in {"openrouter/free", "free"} or or_model.endswith("/free")

    ):

        problems.append(

            "OPENROUTER_MODEL must be a named chat model for public beta "

            "(openrouter/free is not allowed)"

        )

    if _flag_on("NEXA_LOCAL_DESKTOP"):

        problems.append(

            "NEXA_LOCAL_DESKTOP=1 is forbidden on public/cloud hosts "

            "(OS tools are for Electron desktop only)"

        )

    if _flag_on("NEXA_ELECTRON_ALLOW_LAN_BIND"):

        problems.append(

            "NEXA_ELECTRON_ALLOW_LAN_BIND=1 must not be set on public/cloud hosts"

        )

    if _flag_on("NEXA_ALLOW_PACKAGED_DEVTOOLS"):

        problems.append(

            "NEXA_ALLOW_PACKAGED_DEVTOOLS=1 must not be set on public/cloud hosts"

        )

    backend = (settings.memory_backend or "").strip().lower()

    if backend and backend != "sql":

        problems.append("MEMORY_BACKEND must be sql for durable multi-user memory")

    if not (settings.auth_public_base_url or "").strip():

        problems.append("AUTH_PUBLIC_BASE_URL must be the public HTTPS origin")

    email_provider = (getattr(settings, "email_provider", None) or "").strip().lower()

    if email_provider != "smtp":

        problems.append(

            "EMAIL_PROVIDER must be smtp for public beta "

            "(console delivery is not email verification)"

        )

    if not (getattr(settings, "smtp_host", None) or "").strip():

        problems.append("SMTP_HOST must be set when EMAIL_PROVIDER=smtp")

    if not (getattr(settings, "email_from", None) or "").strip():

        problems.append("EMAIL_FROM must be set for verification mail")

    origins = settings.cors_allowed_origins

    if not origins:

        problems.append("CORS_ALLOWED_ORIGINS must list the public HTTPS origin")

    elif all("localhost" in o or "127.0.0.1" in o for o in origins):

        problems.append(

            "CORS_ALLOWED_ORIGINS still lists only localhost — set the public HTTPS origin"

        )

    mode = (settings.nexa_storage_mode or "").strip().lower()

    if bool(getattr(settings, "nexa_public_beta", False)) and mode == "ephemeral":

        problems.append(

            "NEXA_PUBLIC_BETA requires NEXA_STORAGE_MODE=persistent "

            "(ephemeral disk loses accounts on restart)"

        )

    if settings.workflows_enabled:
        problems.append(
            "WORKFLOWS_ENABLED must be false for public/durable hosting until "
            "workflow state is stored in a shared durable database"
        )

    worker_values = {
        name: (os.environ.get(name) or "").strip()
        for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS", "GUNICORN_WORKERS")
        if (os.environ.get(name) or "").strip()
    }
    for name, raw_value in worker_values.items():
        try:
            worker_count = int(raw_value)
        except ValueError:
            problems.append(f"{name} must be an integer and set to 1 for the current single-process architecture")
            continue
        if worker_count != 1:
            problems.append(f"{name} must be 1; NEXA currently requires one application worker")


    return problems





def assert_durable_production(settings: Settings) -> None:

    """Raise if durable production or open-beta config is unsafe."""

    problems = validate_production_settings(settings)

    if not problems:

        return

    label = "open public beta" if getattr(settings, "nexa_public_beta", False) else "durable production"

    msg = f"Unsafe {label} configuration:\n- " + "\n- ".join(problems)

    logger.error(msg)

    raise ProductionConfigError(msg)





def assert_public_cloud(settings: Settings) -> None:

    """Alias used at startup — same hard fail as assert_durable_production."""

    assert_durable_production(settings)


