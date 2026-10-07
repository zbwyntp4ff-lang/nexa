"""Data models for the NEXA voice subsystem."""
from __future__ import annotations
from pydantic import BaseModel, Field
class TranscriptionResult(BaseModel):
    """The output of a speech-to-text call."""
    text: str
    provider: str
    language: str | None = None
    metadata: dict = Field(default_factory=dict)
class SynthesisResult(BaseModel):
    """The output of a text-to-speech call."""
    audio: bytes
    mime_type: str
    provider: str
    voice: str | None = None
    metadata: dict = Field(default_factory=dict)
