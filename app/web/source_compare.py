"""Compare independent research sources for fact corroboration.

Does not invent agreement — only reports token/claim overlap and conflicts.
"""
from __future__ import annotations

import re
from typing import Any

from app.web.models import PageDocument

_WORD = re.compile(r"[a-zа-яё0-9]{4,}", re.I)
_FACTISH = re.compile(
    r"(?i)\b(\d{4}|\d+%|billion|million|млрд|млн|founded|launched|acquired)\b"
)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD.findall(text or "")}


def compare_sources(
    documents: list[PageDocument],
    *,
    claim_hints: list[str] | None = None,
) -> dict[str, Any]:
    """Return a corroboration summary across fetched pages.

    Status meanings:
    - ``insufficient_sources``: fewer than 2 pages
    - ``partial``: some overlap but claims not independently confirmed
    - ``corroborated``: key tokens/claims appear in ≥2 distinct hosts
    - ``conflict_signals``: numeric/year markers disagree across sources
    """
    if len(documents) < 2:
        return {
            "status": "insufficient_sources",
            "source_count": len(documents),
            "note": "Need at least two independent sources to corroborate facts.",
            "shared_tokens": [],
            "conflicts": [],
            "per_source": [],
        }

    per_source: list[dict[str, Any]] = []
    host_tokens: dict[str, set[str]] = {}
    for doc in documents:
        host = (doc.url or "").split("/")[2] if "://" in (doc.url or "") else "unknown"
        toks = _tokens(doc.text or "")
        host_tokens.setdefault(host, set()).update(toks)
        per_source.append(
            {
                "url": doc.url,
                "title": doc.title,
                "host": host,
                "token_count": len(toks),
                "has_date": bool(getattr(doc, "timestamp", None)),
                "factish_hits": len(_FACTISH.findall(doc.text or "")),
            }
        )

    hosts = list(host_tokens.keys())
    shared: set[str] = set.intersection(*(host_tokens[h] for h in hosts)) if hosts else set()
    # Drop ultra-common stop-ish tokens already filtered by length≥4
    shared_list = sorted(shared)[:40]

    claim_hits: list[dict[str, Any]] = []
    for claim in claim_hints or []:
        c = claim.strip().lower()
        if not c:
            continue
        hosts_with: list[str] = []
        for doc in documents:
            host = (doc.url or "").split("/")[2] if "://" in (doc.url or "") else "unknown"
            blob = f"{doc.title or ''} {doc.text or ''}".lower()
            if c in blob and host not in hosts_with:
                hosts_with.append(host)
        claim_hits.append(
            {
                "claim": claim,
                "host_count": len(hosts_with),
                "hosts": hosts_with,
                "corroborated": len(hosts_with) >= 2,
            }
        )

    # Conflict heuristic: distinct 4-digit years per host with low shared tokens
    years_by_host: dict[str, set[str]] = {}
    for doc in documents:
        host = (doc.url or "").split("/")[2] if "://" in (doc.url or "") else "unknown"
        years = set(re.findall(r"\b(19|20)\d{2}\b", doc.text or ""))
        years_by_host.setdefault(host, set()).update(years)
    conflicts: list[str] = []
    all_years = [y for ys in years_by_host.values() for y in ys]
    if len(set(all_years)) >= 4 and len(shared_list) < 3:
        conflicts.append("Multiple distinct year markers with low lexical overlap across hosts.")

    corroborated_claims = sum(1 for c in claim_hits if c["corroborated"])
    if conflicts:
        status = "conflict_signals"
    elif corroborated_claims >= 1 or len(shared_list) >= 8:
        status = "corroborated"
    else:
        status = "partial"

    return {
        "status": status,
        "source_count": len(documents),
        "distinct_hosts": len(hosts),
        "shared_tokens": shared_list,
        "claim_checks": claim_hits,
        "conflicts": conflicts,
        "per_source": per_source,
        "note": (
            "Treat uncorroborated specifics as ASSUMPTION/unverified. "
            "Only claims seen on ≥2 hosts are marked corroborated."
        ),
    }
