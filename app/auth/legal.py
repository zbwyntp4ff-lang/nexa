"""License / terms / privacy documents. Drop files in data/legal/ to override."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.auth.documents import ConsentDocument

HolderKind = Literal["individual", "sole_proprietor", "company"]

HOLDER_KINDS: tuple[HolderKind, ...] = ("individual", "sole_proprietor", "company")

KIND_LABELS_RU: dict[str, str] = {
    "individual": "физическое лицо",
    "sole_proprietor": "индивидуальный предприниматель",
    "company": "юридическое лицо",
}

KIND_LABELS_EN: dict[str, str] = {
    "individual": "natural person",
    "sole_proprietor": "sole proprietor",
    "company": "legal entity",
}

_FILENAMES: dict[ConsentDocument, tuple[str, ...]] = {
    "terms_of_service": ("terms_of_service.md", "terms.md", "terms.txt"),
    "privacy_policy": ("privacy_policy.md", "privacy.md", "privacy.txt"),
    "license_agreement": (
        "license_agreement.md",
        "license.md",
        "LICENSE.md",
        "LICENSE",
        "license.txt",
    ),
}


def legal_dir(settings: Any) -> Path:
    raw = getattr(settings, "auth_legal_dir", None) or "data/legal"
    return Path(str(raw))


def _owner_name(owner: Any | None) -> str:
    if owner is None:
        return ""
    first = str(getattr(owner, "first_name", "") or "").strip()
    last = str(getattr(owner, "last_name", "") or "").strip()
    return " ".join(part for part in (first, last) if part)


def _owner_email(owner: Any | None) -> str:
    if owner is None:
        return ""
    return _clean_contact(str(getattr(owner, "email", "") or ""))


def _clean_contact(raw: str) -> str:
    return raw.strip().lstrip("•·∙●■▪ ")


def load_holder(settings: Any, owner: Any | None = None) -> dict[str, Any]:
    stored: dict[str, Any] = {}
    path = legal_dir(settings) / "holder.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            raw = None
        if isinstance(raw, dict):
            stored = raw

    env_name = str(getattr(settings, "auth_legal_holder_name", "") or "").strip()
    env_kind = str(getattr(settings, "auth_legal_holder_kind", "") or "").strip()
    env_contact = str(getattr(settings, "auth_legal_contact", "") or "").strip()
    env_inn = str(getattr(settings, "auth_legal_inn", "") or "").strip()

    kind = str(stored.get("kind") or env_kind or "individual").strip()
    if kind not in HOLDER_KINDS:
        kind = "individual"

    name = str(stored.get("name") or env_name or _owner_name(owner) or "").strip()
    if not name:
        name = "владелец данной установки NEXA"

    contact = _clean_contact(str(stored.get("contact") or env_contact or _owner_email(owner) or ""))
    inn = str(stored.get("inn") or env_inn or "").strip()
    country = str(stored.get("country") or "RU").strip().upper() or "RU"
    year = datetime.now(timezone.utc).year

    return {
        "name": name,
        "kind": kind,
        "kind_label": KIND_LABELS_RU[kind],
        "kind_label_en": KIND_LABELS_EN[kind],
        "contact": contact,
        "inn": inn,
        "country": country,
        "year": year,
    }


def save_holder(settings: Any, payload: dict[str, Any], owner: Any | None = None) -> dict[str, Any]:
    kind = str(payload.get("kind") or "individual").strip()
    if kind not in HOLDER_KINDS:
        raise ValueError("Unknown holder kind.")
    name = str(payload.get("name") or "").strip()
    if len(name) < 2:
        raise ValueError("Holder name is required.")
    cleaned = {
        "name": name[:200],
        "kind": kind,
        "contact": str(payload.get("contact") or "").strip()[:200],
        "inn": str(payload.get("inn") or "").strip()[:20],
        "country": (str(payload.get("country") or "RU").strip().upper() or "RU")[:2],
    }
    folder = legal_dir(settings)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "holder.json"
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return load_holder(settings, owner=owner)


def list_documents(settings: Any, owner: Any | None = None) -> list[dict[str, str]]:
    from app.auth.documents import DOCUMENT_VERSIONS

    folder = legal_dir(settings)
    items: list[dict[str, str]] = []
    for doc in ("terms_of_service", "privacy_policy", "license_agreement"):
        override = _read_override(folder, doc)  # type: ignore[arg-type]
        items.append(
            {
                "id": doc,
                "version": DOCUMENT_VERSIONS[doc],  # type: ignore[index]
                "source": "file" if override else "builtin",
            }
        )
    return items


def get_document(settings: Any, doc_id: str, owner: Any | None = None) -> dict[str, str]:
    from app.auth.documents import DOCUMENT_VERSIONS

    if doc_id not in _FILENAMES:
        raise KeyError(doc_id)
    typed: ConsentDocument = doc_id  # type: ignore[assignment]
    folder = legal_dir(settings)
    override = _read_override(folder, typed)
    holder = load_holder(settings, owner=owner)
    body = override or _builtin_body(typed, holder)
    return {
        "id": typed,
        "version": DOCUMENT_VERSIONS[typed],
        "source": "file" if override else "builtin",
        "body": body,
    }


def _read_override(folder: Path, doc: ConsentDocument) -> str | None:
    if not folder.is_dir():
        return None
    for name in _FILENAMES[doc]:
        if name.lower() == "holder.json":
            continue
        path = folder / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                continue
            if text:
                return text
    return None


def _holder_block(holder: dict[str, Any]) -> tuple[str, str]:
    inn_ru = f"\nИНН: {holder['inn']}" if holder.get("inn") else ""
    inn_en = f"\nTax ID: {holder['inn']}" if holder.get("inn") else ""
    contact = holder.get("contact") or "учётная запись владельца установки"
    contact_en = holder.get("contact") or "the installation owner account"
    ru = (
        f"Правообладатель: {holder['name']}\n"
        f"Статус: {holder['kind_label']}\n"
        f"Страна: {holder['country']}"
        f"{inn_ru}\n"
        f"Контакт: {contact}\n"
        f"Год: {holder['year']}"
    )
    en = (
        f"Rights holder: {holder['name']}\n"
        f"Status: {holder['kind_label_en']}\n"
        f"Country: {holder['country']}"
        f"{inn_en}\n"
        f"Contact: {contact_en}\n"
        f"Year: {holder['year']}"
    )
    return ru, en


def _builtin_body(doc: ConsentDocument, holder: dict[str, Any]) -> str:
    ru_block, en_block = _holder_block(holder)
    if doc == "license_agreement":
        return (
            "# Лицензионное соглашение NEXA\n\n"
            "Версия 1.1.0. Все права защищены.\n\n"
            f"{ru_block}\n\n"
            "Программа NEXA — проприетарное программное обеспечение. "
            "Правообладатель предоставляет вам личную, неисключительную и непередаваемую "
            "лицензию на использование этой установки.\n\n"
            "Запрещается без письменного согласия правообладателя копировать, "
            "распространять, сдавать в аренду, продавать программу, обходить защиту "
            "и лимиты, а также передавать ключи провайдеров или данные других пользователей.\n\n"
            "Загружая файлы, вы подтверждаете, что имеете право ими пользоваться. "
            "Программа предоставляется «как есть». Если правообладатель находится "
            "в Российской Федерации, применяется право Российской Федерации.\n\n"
            "---\n\n"
            "# NEXA License Agreement\n\n"
            "Version 1.1.0. All rights reserved.\n\n"
            f"{en_block}\n\n"
            "NEXA is proprietary software. The rights holder grants you a personal, "
            "non-exclusive, non-transferable license to use this installation. "
            "Redistribution of the software, provider API keys, or other users' data "
            "is not allowed without written permission.\n"
        )
    if doc == "terms_of_service":
        return (
            "# Пользовательское соглашение NEXA\n\n"
            "Версия 1.1.0.\n\n"
            f"{ru_block}\n\n"
            "Создавая аккаунт или пользуясь NEXA, вы соглашаетесь использовать программу "
            "законно, хранить данные входа в тайне и не обходить ограничения безопасности "
            "и лимиты. Правообладатель может ограничить доступ при нарушении этих правил.\n\n"
            "---\n\n"
            "# NEXA Terms of Service\n\n"
            "Version 1.1.0.\n\n"
            f"{en_block}\n\n"
            "By creating or using a NEXA account you agree to use the software lawfully, "
            "keep your login details private, and not attempt to bypass usage limits or "
            "security controls.\n"
        )
    return (
        "# Политика конфиденциальности NEXA\n\n"
        "Версия 1.1.0.\n\n"
        f"{ru_block}\n\n"
        "Данные аккаунта, Memory, Knowledge и файлы этой установки хранятся на машине "
        "или сервере, где запущена NEXA. Локальный кэш чатов в браузере не означает, "
        "что сообщения никуда не уходят: при каждом запросе текст отправляется на backend "
        "и дальше — выбранному AI-провайдеру (OpenAI, Anthropic, локальный Ollama и т.п.). "
        "Research может обращаться к поисковикам и загружать страницы; оплата — к Stripe; "
        "вход через Google/GitHub/Apple — к соответствующему IdP; HEXA может использовать "
        "облачное распознавание речи браузера. Правообладатель не продаёт ваши данные.\n\n"
        "---\n\n"
        "# NEXA Privacy Policy\n\n"
        "Version 1.1.0.\n\n"
        f"{en_block}\n\n"
        "Account data, Memory, Knowledge, and files for this installation live on the "
        "machine or server that runs NEXA. A browser-local chat cache does not mean "
        "messages stay offline: each request is sent to the NEXA backend and then to "
        "the selected AI provider (OpenAI, Anthropic, local Ollama, etc.). Research may "
        "query search engines and fetch pages; billing uses Stripe; Google/GitHub/Apple "
        "sign-in contacts those IdPs; HEXA may use the browser's cloud speech service. "
        "The rights holder does not sell your data.\n"
    )
