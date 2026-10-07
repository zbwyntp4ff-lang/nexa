"""Structured Knowledge Core models — rule packs, not a giant prompt blob."""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class IntentKind(str, Enum):
    GENERAL = "general"
    BUILD = "build"
    CODE = "code"
    RESEARCH = "research"
    SHADOW = "shadow"
    FORGE = "forge"
    BREAKTHROUGH = "breakthrough"
    DESIGN = "design"
    SEARCH = "search"
    CAPABILITY = "capability"


class RulePack(BaseModel):
    """One loadable pack of behavioral / domain rules."""

    id: str
    title: str
    always: bool = False
    intents: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    priority: int = 100
    max_chars: int = 500
    rules: list[str] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    epistemic_labels: list[str] = Field(default_factory=list)


class ComposeResult(BaseModel):
    """Compact fragment ready to inject as system context."""

    intents: list[IntentKind]
    pack_ids: list[str]
    text: str
    char_count: int
