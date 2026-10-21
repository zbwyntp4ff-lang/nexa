"""Measurable RAG retrieval evaluation — hashing embeddings vs local baselines.

No paid embedding APIs. Compares:
- ``hashing256`` / ``hashing512``: LocalEmbeddingProvider
- ``token_overlap``: non-embedding baseline (query/doc token Jaccard ranking)

Writes a machine-readable JSON report under ``data/eval_reports/``.
"""
from __future__ import annotations

import json
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.paths import resolve_under_project_root
from app.knowledge.embeddings import LocalEmbeddingProvider, _tokenize, cosine_similarity


@dataclass
class QueryCase:
    query: str
    relevant_doc_ids: list[str]


@dataclass
class RankedHit:
    doc_id: str
    score: float


def recall_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(ranked[:k])
    return len(relevant & top) / len(relevant)


def precision_at_k(relevant: set[str], ranked: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = ranked[:k]
    if not top:
        return 0.0
    return sum(1 for d in top if d in relevant) / len(top)


def mrr(relevant: set[str], ranked: list[str]) -> float:
    for i, doc_id in enumerate(ranked, start=1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def _rank_hashing(
    query: str, docs: dict[str, str], *, dimensions: int
) -> list[RankedHit]:
    emb = LocalEmbeddingProvider(dimensions=dimensions)
    qv = emb.embed(query)
    scored = [
        RankedHit(doc_id=doc_id, score=cosine_similarity(qv, emb.embed(text)))
        for doc_id, text in docs.items()
    ]
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored


def _rank_token_overlap(query: str, docs: dict[str, str]) -> list[RankedHit]:
    q = {t for t in _tokenize(query) if len(t) > 2}
    scored: list[RankedHit] = []
    for doc_id, text in docs.items():
        d = {t for t in _tokenize(text) if len(t) > 2}
        if not q or not d:
            score = 0.0
        else:
            score = len(q & d) / len(q | d)
        scored.append(RankedHit(doc_id=doc_id, score=score))
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored


DEFAULT_CORPUS: dict[str, str] = {
    "d_fastapi": (
        "FastAPI is a Python web framework for building APIs with type hints. "
        "It uses Starlette and Pydantic. Dependency injection and OpenAPI are built-in."
    ),
    "d_rag": (
        "Retrieval Augmented Generation (RAG) embeds documents, stores vectors, "
        "and retrieves relevant chunks to ground LLM answers with citations."
    ),
    "d_pptx": (
        "PowerPoint PPTX files are ZIP packages with slides, shapes, and text frames. "
        "python-pptx can create editable presentations programmatically."
    ),
    "d_ssrf": (
        "SSRF protection blocks requests to localhost, private IP ranges, and file:// "
        "schemes when fetching user-supplied URLs on the server."
    ),
    "d_finance": (
        "Unit economics for SaaS include ARPU, CAC, LTV, and gross margin. "
        "ASSUMPTION placeholders must not be presented as measured market facts."
    ),
    # RU + EN, paraphrases, near-miss distractors, long doc, multi-source
    "d_ru_memory": (
        "Память NEXA хранит факты пользователя между сессиями. "
        "Поиск по памяти использует лимиты MEMORY_SEARCH_LIMIT и не подменяет ответы модели."
    ),
    "d_ru_browser": (
        "BrowserTool открывает публичные http(s) страницы через Playwright. "
        "Доступ к localhost и file:// блокируется SSRF-политикой."
    ),
    "d_bank_rates": (
        "Central bank policy rates are set by monetary authorities to influence inflation. "
        "This document is about interest rates, not about software frameworks."
    ),
    "d_java_spring": (
        "Spring Boot is a Java framework for microservices with dependency injection. "
        "It is similar in wording to FastAPI docs but targets the JVM ecosystem."
    ),
    "d_long_office": (
        "Office deliverables in NEXA. " * 40
        + "PPTX presentations are created with python-pptx. "
        + "XLSX spreadsheets may include Excel formulas for totals. "
        + "DOCX reports use python-docx paragraphs. "
        + "PDF export is a separate tool. " * 20
    ),
    "d_multi_a": (
        "ChatGPT is an OpenAI assistant product with a Plus subscription tier. "
        "API access is sold separately via the OpenAI platform."
    ),
    "d_multi_b": (
        "Claude is an Anthropic assistant. API access is available via Anthropic Console. "
        "Consumer chat and API billing are distinct products."
    ),
}

DEFAULT_CASES: list[QueryCase] = [
    QueryCase("How does FastAPI dependency injection work?", ["d_fastapi"]),
    QueryCase("What is RAG vector retrieval?", ["d_rag"]),
    QueryCase("Create editable PowerPoint slides with python", ["d_pptx"]),
    QueryCase("Block private network URL fetches SSRF", ["d_ssrf"]),
    QueryCase("SaaS ARPU CAC LTV unit economics", ["d_finance"]),
    QueryCase("astronomy black holes cosmology", []),  # no relevant doc
    # RU paraphrase
    QueryCase("Как NEXA сохраняет факты о пользователе между сеансами?", ["d_ru_memory"]),
    QueryCase("Почему браузерный инструмент не открывает localhost?", ["d_ru_browser"]),
    # EN paraphrase of FastAPI
    QueryCase("Which Python API framework uses Starlette and Pydantic?", ["d_fastapi"]),
    # Similar words, different meaning (Spring vs FastAPI)
    QueryCase("Java microservices dependency injection framework Spring", ["d_java_spring"]),
    # Distractor: rates vs finance SaaS
    QueryCase("central bank interest rates inflation policy", ["d_bank_rates"]),
    # Long document
    QueryCase("Where do Excel formulas appear in NEXA office deliverables?", ["d_long_office"]),
    # Multi-source relevant
    QueryCase("OpenAI ChatGPT Plus versus API billing", ["d_multi_a"]),
    QueryCase("Anthropic Claude API console access", ["d_multi_b"]),
    # Absence
    QueryCase("курс биткоина прямо сейчас точная цена", []),
]


def evaluate_retrievers(
    *,
    corpus: dict[str, str] | None = None,
    cases: list[QueryCase] | None = None,
    k: int = 3,
) -> dict[str, Any]:
    docs = corpus or DEFAULT_CORPUS
    queries = cases or DEFAULT_CASES
    methods = {
        "hashing256": lambda q: _rank_hashing(q, docs, dimensions=256),
        "hashing512": lambda q: _rank_hashing(q, docs, dimensions=512),
        "token_overlap": lambda q: _rank_token_overlap(q, docs),
    }
    report: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "n_docs": len(docs),
        "n_queries": len(queries),
        "methods": {},
        "recommendation": "",
    }
    for name, rank_fn in methods.items():
        recalls: list[float] = []
        precisions: list[float] = []
        mrrs: list[float] = []
        latencies: list[float] = []
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        for case in queries:
            t0 = time.perf_counter()
            ranked = [h.doc_id for h in rank_fn(case.query)]
            latencies.append((time.perf_counter() - t0) * 1000)
            rel = set(case.relevant_doc_ids)
            if not rel:
                # No-relevant queries: precision should stay low if junk ranks high —
                # skip recall/mrr contribution.
                continue
            recalls.append(recall_at_k(rel, ranked, k))
            precisions.append(precision_at_k(rel, ranked, k))
            mrrs.append(mrr(rel, ranked))
        after = tracemalloc.take_snapshot()
        stats = after.compare_to(before, "lineno")
        mem_kb = sum(s.size_diff for s in stats[:50]) / 1024.0
        tracemalloc.stop()
        report["methods"][name] = {
            "recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else None,
            "precision_at_k": round(sum(precisions) / len(precisions), 4) if precisions else None,
            "mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else None,
            "latency_ms_avg": round(sum(latencies) / len(latencies), 3) if latencies else None,
            "latency_ms_p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 3)
            if latencies
            else None,
            "approx_alloc_kb": round(mem_kb, 2),
            "cost_usd": 0.0,
            "paid_api": False,
        }

    # Prefer hashing256 as default: free, already wired, competitive on this set.
    # Recommend hashing512 only if recall clearly higher without large latency hit.
    h256 = report["methods"]["hashing256"]
    h512 = report["methods"]["hashing512"]
    overlap = report["methods"]["token_overlap"]
    if (
        h512["recall_at_k"] is not None
        and h256["recall_at_k"] is not None
        and h512["recall_at_k"] > h256["recall_at_k"] + 0.05
    ):
        report["recommendation"] = (
            "hashing512 shows higher Recall@k on this fixture; keep default hashing256 "
            "unless reindex cost is acceptable. No paid embedding API enabled."
        )
    else:
        report["recommendation"] = (
            "Keep LocalEmbeddingProvider hashing256 as default (free, zero reindex risk). "
            f"token_overlap MRR={overlap['mrr']} is a non-embedding baseline only."
        )
    return report


def write_rag_eval_report(report: dict[str, Any] | None = None) -> Path:
    data = report or evaluate_retrievers()
    out_dir = resolve_under_project_root("data/eval_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "rag_retrieval.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
