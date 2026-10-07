"""Load Knowledge Core packs from ``data/knowledge_core/packs``."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.logging_config import get_logger
from app.core.paths import resolve_under_project_root
from app.knowledge_core.models import RulePack

logger = get_logger("nexa.knowledge_core")

_PACKS_DIR = resolve_under_project_root("data/knowledge_core/packs")


def packs_dir() -> Path:
    return _PACKS_DIR


@lru_cache
def load_packs() -> tuple[RulePack, ...]:
    directory = packs_dir()
    if not directory.exists():
        logger.warning("knowledge core packs directory missing: %s", directory)
        return ()
    packs: list[RulePack] = []
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            packs.append(RulePack.model_validate(raw))
        except Exception:  # noqa: BLE001
            logger.warning("skipped invalid knowledge core pack: %s", path.name)
    logger.info("knowledge core loaded packs=%d", len(packs))
    return tuple(packs)


def reload_packs() -> tuple[RulePack, ...]:
    load_packs.cache_clear()
    return load_packs()
