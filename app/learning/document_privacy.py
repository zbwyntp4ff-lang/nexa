"""Privacy-aware model routing for requests containing user documents."""
from __future__ import annotations

from typing import Any


def document_routing_options(
    *,
    contains_document_context: bool,
    model: str | None,
    task_kind: Any,
) -> dict[str, Any]:
    """Return gateway arguments that prevent document context reaching cloud models.

    The setting is deliberately checked at request time. If cloud processing is
    disabled, force the gateway's LOCAL policy, bypass any persisted manual cloud
    selection, and disable fallback. If no local model is available, the gateway
    must fail rather than send private context to a cloud provider.
    """
    if not contains_document_context:
        return {"model": model, "task_kind": task_kind}

    from app.learning.settings import get_learning_settings

    if get_learning_settings().allow_cloud_on_documents:
        return {"model": model, "task_kind": task_kind}

    from app.gateway.models import TaskKind

    return {
        "model": "auto",
        "task_kind": TaskKind.LOCAL,
        "allow_fallback": False,
    }


def local_provider_is_safe(provider_name: str) -> bool:
    """Whether a non-gateway provider is known to execute locally."""
    return provider_name.strip().lower() in {"ollama", "local", "mock"}
