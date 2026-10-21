"""Phase 6 beta evaluation cases — RU primary, EN for multilingual check.

Scoring is objective where possible (contains/regex/clarification/unknown).
Subjective quality is never invented; live runs store raw answers for review.
"""
from __future__ import annotations

from typing import Any

# Minimum 30 Russian + English coverage across required categories.
BETA_CASES: list[dict[str, Any]] = [
    # --- general knowledge (RU) ---
    {
        "id": "ru_gk_01",
        "lang": "ru",
        "category": "general_knowledge",
        "prompt": "Столица Франции? Один слово.",
        "expect_contains": ["париж"],
    },
    {
        "id": "ru_gk_02",
        "lang": "ru",
        "category": "general_knowledge",
        "prompt": "Сколько планет в Солнечной системе по современным данным МАС (без Плутона)? Число.",
        "expect_regex": r"\b8\b",
    },
    {
        "id": "ru_gk_03",
        "lang": "ru",
        "category": "general_knowledge",
        "prompt": "Кто написал роман «Война и мир»? Фамилия.",
        "expect_contains": ["толст"],
    },
    # --- math / logic (RU) ---
    {
        "id": "ru_math_01",
        "lang": "ru",
        "category": "math",
        "prompt": "Вычисли 17 * 19. Только число.",
        "exact_answer": "323",
        "expect_regex": r"\b323\b",
    },
    {
        "id": "ru_math_02",
        "lang": "ru",
        "category": "math",
        "prompt": "Сколько будет 2^10? Только число.",
        "exact_answer": "1024",
        "expect_regex": r"\b1024\b",
    },
    {
        "id": "ru_logic_01",
        "lang": "ru",
        "category": "logic",
        "prompt": "Все кошки — млекопитающие. Мурка — кошка. Является ли Мурка млекопитающим? Да или нет.",
        "expect_contains": ["да"],
    },
    {
        "id": "ru_logic_02",
        "lang": "ru",
        "category": "logic",
        "prompt": "Если сегодня среда, какой день будет через 2 дня? Одно слово.",
        "expect_contains": ["пятниц"],
    },
    # --- explain complex topics (RU) ---
    {
        "id": "ru_explain_01",
        "lang": "ru",
        "category": "explanation",
        "prompt": "Объясни простыми словами, что такое RAG (Retrieval Augmented Generation) за 3–5 предложений.",
        "expect_regex": r"(?i)rag|поиск|документ|извлеч|retriev|генерац",
        "forbid_equals_prompt": True,
    },
    {
        "id": "ru_explain_02",
        "lang": "ru",
        "category": "explanation",
        "prompt": "Объясни, чем HTTP отличается от HTTPS. Кратко.",
        "expect_regex": r"(?i)tls|ssl|шифр|сертификат|https",
        "forbid_equals_prompt": True,
    },
    {
        "id": "ru_explain_03",
        "lang": "ru",
        "category": "explanation",
        "prompt": "Что такое SSRF-атака в веб-безопасности? 2–4 предложения.",
        "expect_regex": r"(?i)server|запрос|localhost|внутренн|сервер",
        "forbid_equals_prompt": True,
    },
    # --- programming (RU) ---
    {
        "id": "ru_code_01",
        "lang": "ru",
        "category": "programming",
        "prompt": "Напиши функцию на Python, которая возвращает факториал n. Только код.",
        "expect_regex": r"(?i)def\s+\w+\(|factorial|return",
    },
    {
        "id": "ru_code_02",
        "lang": "ru",
        "category": "programming",
        "prompt": "Что выведет: print(sorted([3,1,2]))? Только результат.",
        "expect_contains": ["[1, 2, 3]"],
    },
    {
        "id": "ru_code_03",
        "lang": "ru",
        "category": "programming",
        "prompt": "Исправь ошибку: for i in range(3) print(i)",
        "expect_regex": r":\s*\n|:\s*print|for i in range\(3\):",
    },
    # --- data analysis (RU) ---
    {
        "id": "ru_data_01",
        "lang": "ru",
        "category": "data_analysis",
        "prompt": (
            "Данные: выручка Q1=100, Q2=120, Q3=150. "
            "На сколько процентов выросла выручка от Q1 к Q3? Число."
        ),
        "expect_regex": r"\b50\b",
    },
    {
        "id": "ru_data_02",
        "lang": "ru",
        "category": "data_analysis",
        "prompt": (
            "Таблица: A=10, B=20, C=30. Среднее арифметическое? Число."
        ),
        "exact_answer": "20",
        "expect_regex": r"\b20\b",
    },
    {
        "id": "ru_data_03",
        "lang": "ru",
        "category": "data_analysis",
        "prompt": (
            "Фрагмент отчёта: «CAC = $40, LTV = $200». Какой LTV:CAC? Число."
        ),
        "expect_regex": r"\b5\b",
    },
    # --- search / fresh info (RU) — scored for honesty if no tool ---
    {
        "id": "ru_search_01",
        "lang": "ru",
        "category": "search",
        "prompt": (
            "Какая актуальная цена подписки ChatGPT Plus в USD на сегодня? "
            "Если нет доступа к интернету — так и скажи."
        ),
        "expect_admits_unknown_or_contains": ["не знаю", "нет доступа", "не могу", "без поиска", "$20", "20"],
    },
    {
        "id": "ru_search_02",
        "lang": "ru",
        "category": "search",
        "prompt": "Кто выиграл последний суперкубок NFL? Если данных нет — признай неизвестность.",
        "expect_admits_unknown_or_contains": ["не знаю", "нет данных", "уточн", "super bowl", "superbowl"],
    },
    # --- competitor compare (RU) ---
    {
        "id": "ru_cmp_01",
        "lang": "ru",
        "category": "comparison",
        "prompt": (
            "Сравни ChatGPT, Claude и Gemini по трём критериям: доступность API, "
            "сильные стороны, типичные ограничения. Таблицей markdown. "
            "Не выдумывай точные цены без оговорки ASSUMPTION."
        ),
        "expect_regex": r"(?i)chatgpt|claude|gemini",
        "forbid_equals_prompt": True,
    },
    {
        "id": "ru_cmp_02",
        "lang": "ru",
        "category": "comparison",
        "prompt": "Чем Notion AI отличается от обычного Notion без AI? Кратко, без выдуманных метрик.",
        "expect_regex": r"(?i)ai|помощник|генерац|автомат",
        "forbid_equals_prompt": True,
    },
    # --- document generation intent (RU) ---
    {
        "id": "ru_doc_01",
        "lang": "ru",
        "category": "document_generation",
        "prompt": (
            "Составь краткий план Word-отчёта (5 заголовков) по сравнению AI-ассистентов."
        ),
        "expect_regex": r"(?i)1[\.\)]|введен|сравнен|вывод",
        "forbid_equals_prompt": True,
    },
    {
        "id": "ru_doc_02",
        "lang": "ru",
        "category": "document_generation",
        "prompt": "Перечисли 10 тем слайдов для презентации «Рынок AI-ассистентов 2026».",
        "expect_regex": r"(?i)1[\.\):]|слайд|рынок|конкурент",
        "forbid_equals_prompt": True,
    },
    # --- multi-step (RU) ---
    {
        "id": "ru_multi_01",
        "lang": "ru",
        "category": "multi_step",
        "prompt": (
            "Составь план из 5 шагов: исследовать конкурентов, сделать таблицу, "
            "собрать презентацию, написать отчёт, сохранить в папку проекта."
        ),
        "expect_regex": r"(?i)1[\.\)]|исследова|таблиц|презента|отч[её]т|папк",
    },
    {
        "id": "ru_multi_02",
        "lang": "ru",
        "category": "multi_step",
        "prompt": (
            "Разбей задачу: «найти 3 источника про Claude и суммировать» на подзадачи. Список."
        ),
        "expect_regex": r"(?i)1[\.\)]|поиск|источник|сумм",
    },
    # --- ambiguous / missing data (RU) ---
    {
        "id": "ru_amb_01",
        "lang": "ru",
        "category": "ambiguous",
        "prompt": "Сделай это получше.",
        "expect_asks_clarification": True,
    },
    {
        "id": "ru_amb_02",
        "lang": "ru",
        "category": "ambiguous",
        "prompt": "Исправь баг.",
        "expect_asks_clarification": True,
    },
    {
        "id": "ru_miss_01",
        "lang": "ru",
        "category": "missing_data",
        "prompt": "Какой был наш ARR в Q3 по филиалу Acme в Казани?",
        "expect_admits_unknown": True,
    },
    {
        "id": "ru_miss_02",
        "lang": "ru",
        "category": "missing_data",
        "prompt": "Сколько пользователей у нашего закрытого продукта NEXA_INTERNAL_XYZ прямо сейчас?",
        "expect_admits_unknown": True,
    },
    {
        "id": "ru_miss_03",
        "lang": "ru",
        "category": "missing_data",
        "prompt": "Назови точную цену нашего enterprise-тарифа NEXA Pro Enterprise 2024.",
        "expect_admits_unknown": True,
    },
    {
        "id": "ru_quality_01",
        "lang": "ru",
        "category": "quality",
        "prompt": "Что такое гравитация?",
        "forbid_equals_prompt": True,
        "expect_regex": r"(?i)притяжен|масса|сила|земл",
    },
    # --- English multilingual ---
    {
        "id": "en_gk_01",
        "lang": "en",
        "category": "general_knowledge",
        "prompt": "Capital of Japan? One word.",
        "expect_contains": ["tokyo"],
    },
    {
        "id": "en_math_01",
        "lang": "en",
        "category": "math",
        "prompt": "Compute 25 * 37. Number only.",
        "exact_answer": "925",
        "expect_regex": r"\b925\b",
    },
    {
        "id": "en_code_01",
        "lang": "en",
        "category": "programming",
        "prompt": "Write a Python one-liner to reverse string s.",
        "expect_regex": r"s\[::-1\]|reversed\(",
    },
    {
        "id": "en_explain_01",
        "lang": "en",
        "category": "explanation",
        "prompt": "Explain SSRF in two sentences.",
        "expect_regex": r"(?i)server|request|internal|localhost",
        "forbid_equals_prompt": True,
    },
    {
        "id": "en_amb_01",
        "lang": "en",
        "category": "ambiguous",
        "prompt": "Make it better.",
        "expect_asks_clarification": True,
    },
    {
        "id": "en_miss_01",
        "lang": "en",
        "category": "missing_data",
        "prompt": "What was our Q3 ARR last year for the Acme subsidiary?",
        "expect_admits_unknown": True,
    },
    {
        "id": "en_cmp_01",
        "lang": "en",
        "category": "comparison",
        "prompt": (
            "Compare ChatGPT vs Claude vs Gemini on API availability and limits. "
            "Mark unknown prices as ASSUMPTION."
        ),
        "expect_regex": r"(?i)chatgpt|claude|gemini",
        "forbid_equals_prompt": True,
    },
    {
        "id": "en_multi_01",
        "lang": "en",
        "category": "multi_step",
        "prompt": "List 4 steps to research competitors then produce an Excel comparison.",
        "expect_regex": r"(?i)1[\.\)]|research|excel|compar",
    },
]

assert len([c for c in BETA_CASES if c["lang"] == "ru"]) >= 30
assert len([c for c in BETA_CASES if c["lang"] == "en"]) >= 5
