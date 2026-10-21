"""Phase 6 beta model evaluation — real providers only for quality claims.

MockProvider is rejected for quality reports. Usage/cost are recorded only when
the provider returns them; otherwise fields stay null.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root
from app.learning.beta_cases import BETA_CASES
from app.learning.eval_suite import _score_text
from app.models.chat import ChatMessage, ChatRole
from app.models.errors import ProviderConfigurationError
from app.providers.factory import ProviderFactory


def _score_beta_case(case: dict[str, Any], text: str) -> dict[str, Any]:
    scored = _score_text(case, text)
    alt = case.get("expect_admits_unknown_or_contains")
    if alt:
        lower = (text or "").strip().lower()
        ok_alt = any(needle.lower() in lower for needle in alt)
        if not ok_alt:
            scored["pass"] = False
            scored["reasons"] = list(scored.get("reasons") or []) + ["unknown_or_contains_miss"]
        elif not scored["pass"] and "missing:" in ",".join(scored.get("reasons") or []):
            # Soft override: if primary expect_contains failed but alt matched
            scored["pass"] = True
            scored["reasons"] = [r for r in (scored.get("reasons") or []) if not str(r).startswith("missing:")]
            scored["reasons"].append("matched_alt_unknown_or_contains")
    return scored


def detect_real_provider() -> dict[str, Any]:
    """Pick a configured real provider. Never falls back to mock for quality."""
    settings = get_settings()
    candidates: list[tuple[str, bool, str]] = [
        ("openrouter", bool(settings.openrouter_api_key), "OPENROUTER_API_KEY"),
        ("anthropic", bool(settings.anthropic_api_key), "ANTHROPIC_API_KEY"),
        ("openai", bool(settings.openai_api_key), "OPENAI_API_KEY"),
        ("gemini", bool(settings.resolved_gemini_api_key), "GEMINI_API_KEY"),
        ("ollama", True, "LOCAL_MODEL_URL (Ollama)"),  # probe separately
        ("local", True, "LOCAL_MODEL_URL"),
    ]
    available = []
    for name, has_key, how in candidates:
        if name in {"ollama", "local"}:
            available.append({"provider": name, "configured": has_key, "how": how})
            continue
        available.append({"provider": name, "configured": has_key, "how": how})

    # Honor explicit non-mock AI_PROVIDER when credentials exist.
    pinned = (settings.ai_provider or "").strip().lower()
    if pinned and pinned != "mock":
        if pinned in {"ollama", "local"}:
            pass  # fall through to ollama probe
        elif pinned == "openrouter" and settings.openrouter_api_key:
            return {
                "provider": "openrouter",
                "model": _model_for(settings, "openrouter"),
                "how": "AI_PROVIDER=openrouter",
                "available": available,
            }
        elif pinned == "anthropic" and settings.anthropic_api_key:
            return {
                "provider": "anthropic",
                "model": _model_for(settings, "anthropic"),
                "how": "AI_PROVIDER=anthropic",
                "available": available,
            }
        elif pinned == "openai" and settings.openai_api_key:
            return {
                "provider": "openai",
                "model": _model_for(settings, "openai"),
                "how": "AI_PROVIDER=openai",
                "available": available,
            }
        elif pinned == "gemini" and settings.resolved_gemini_api_key:
            return {
                "provider": "gemini",
                "model": _model_for(settings, "gemini"),
                "how": "AI_PROVIDER=gemini",
                "available": available,
            }

    # Prefer cloud with key, then ollama
    for name, has_key, how in candidates:
        if name in {"ollama", "local"}:
            continue
        if has_key:
            return {
                "provider": name,
                "model": _model_for(settings, name),
                "how": how,
                "available": available,
            }

    # Probe ollama
    try:
        import urllib.request

        with urllib.request.urlopen(
            f"{settings.local_model_url.rstrip('/')}/api/tags", timeout=2
        ) as resp:
            if resp.status == 200:
                return {
                    "provider": "ollama",
                    "model": settings.local_model_name,
                    "how": "LOCAL_MODEL_URL + ollama serve",
                    "available": available,
                }
    except Exception:  # noqa: BLE001
        pass

    return {
        "provider": None,
        "model": None,
        "how": None,
        "available": available,
        "error": (
            "No real model provider configured. Set one of OPENROUTER_API_KEY, "
            "ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, or run Ollama at "
            "LOCAL_MODEL_URL, then: AI_PROVIDER=<provider> python -m app.learning.beta_eval"
        ),
    }


def _model_for(settings: Any, provider: str) -> str:
    return {
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "gemini": settings.gemini_model,
        "openrouter": settings.openrouter_model,
        "ollama": settings.local_model_name,
        "local": settings.local_model_name,
    }.get(provider, "unknown")


async def _generate_openai_compat(
    *,
    api_key: str,
    model: str,
    base_url: str | None,
    prompt: str,
    timeout: float,
    provider_name: str,
) -> dict[str, Any]:
    """Call OpenAI-compatible chat and capture usage when present."""
    from openai import AsyncOpenAI

    client_kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
    if base_url:
        client_kwargs["base_url"] = base_url.rstrip("/")
    client = AsyncOpenAI(**client_kwargs)
    t0 = time.perf_counter()
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = (time.perf_counter() - t0) * 1000
    text = ""
    if response.choices and response.choices[0].message:
        text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None
    return {
        "text": text,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": None,  # never invent
        "provider": provider_name,
        "model": model,
    }


async def generate_real(prompt: str, *, provider: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    detected = detect_real_provider()
    name = (provider or detected.get("provider") or "").strip().lower()
    if not name or name == "mock":
        raise ProviderConfigurationError(
            detected.get("error")
            or "Real provider required. MockProvider cannot be used for beta quality eval."
        )

    model = _model_for(settings, name)
    timeout = float(settings.request_timeout_seconds or 60)

    if name == "openrouter":
        return await _generate_openai_compat(
            api_key=settings.openrouter_api_key or "",
            model=model,
            base_url=settings.openrouter_base_url,
            prompt=prompt,
            timeout=timeout,
            provider_name="openrouter",
        )
    if name == "openai":
        return await _generate_openai_compat(
            api_key=settings.openai_api_key or "",
            model=model,
            base_url=None,
            prompt=prompt,
            timeout=timeout,
            provider_name="openai",
        )

    # Anthropic / gemini / ollama via factory (no usage unless we add later)
    provider_obj = ProviderFactory.create(settings, provider_override=name)
    t0 = time.perf_counter()
    text = await provider_obj.generate([ChatMessage(role=ChatRole.USER, content=prompt)])
    latency_ms = (time.perf_counter() - t0) * 1000
    return {
        "text": text,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "provider": name,
        "model": getattr(provider_obj, "model_name", model),
    }


async def run_beta_eval(
    *,
    provider: str | None = None,
    limit: int | None = None,
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    detected = detect_real_provider()
    name = provider or detected.get("provider")
    if not name:
        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "suite": "nexa_beta_eval_v1",
            "status": "not_run",
            "reason": detected.get("error"),
            "how_to_run": (
                "1) Configure a real key or Ollama\n"
                "2) AI_PROVIDER=openrouter|anthropic|openai|gemini|ollama\n"
                "3) python -m app.learning.beta_eval\n"
                "MockProvider is for infrastructure tests only."
            ),
            "available": detected.get("available"),
            "cases": [],
            "passed": 0,
            "total": 0,
            "pass_rate": None,
        }

    selected = list(cases or BETA_CASES)
    if limit is not None:
        selected = selected[:limit]

    results: list[dict[str, Any]] = []
    errors = 0
    for case in selected:
        row: dict[str, Any] = {
            "id": case["id"],
            "lang": case["lang"],
            "category": case["category"],
            "prompt": case["prompt"],
            "provider": name,
            "model": _model_for(get_settings(), name),
        }
        try:
            gen = await generate_real(case["prompt"], provider=name)
            scored = _score_beta_case(case, gen["text"])
            row.update(
                {
                    "status": "ok",
                    "latency_ms": gen["latency_ms"],
                    "prompt_tokens": gen.get("prompt_tokens"),
                    "completion_tokens": gen.get("completion_tokens"),
                    "total_tokens": gen.get("total_tokens"),
                    "cost_usd": gen.get("cost_usd"),
                    "answer_preview": (gen["text"] or "")[:400],
                    "pass": scored["pass"],
                    "reasons": scored.get("reasons") or [],
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors += 1
            row.update(
                {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "pass": False,
                    "latency_ms": None,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "cost_usd": None,
                }
            )
        results.append(row)

    passed = sum(1 for r in results if r.get("pass"))
    total = len(results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": "nexa_beta_eval_v1",
        "status": "completed",
        "provider": name,
        "model": _model_for(get_settings(), name),
        "n_ru": sum(1 for c in selected if c["lang"] == "ru"),
        "n_en": sum(1 for c in selected if c["lang"] == "en"),
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else None,
        "errors": errors,
        "notes": (
            "cost_usd is null unless a verified pricing map is applied; "
            "tokens recorded only when the API returns usage. "
            "MockProvider was not used."
        ),
        "cases": results,
    }
    return report


def write_beta_eval_report(report: dict[str, Any] | None = None) -> Path:
    import asyncio

    data = report
    if data is None:
        data = asyncio.run(run_beta_eval())
    out = resolve_under_project_root("data/eval_reports/beta_model_eval.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


async def _amain() -> None:
    report = await run_beta_eval()
    path = write_beta_eval_report(report)
    print(json.dumps({"status": report.get("status"), "path": str(path), "pass_rate": report.get("pass_rate"), "provider": report.get("provider"), "total": report.get("total")}, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(_amain())
