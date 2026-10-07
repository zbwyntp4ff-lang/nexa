"""Data models for the NEXA image generation subsystem."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
class ImageGenerationResult(BaseModel):
    """The output of an image generate/edit call.
    ``images`` holds either URLs or base64-encoded image payloads, per
    ``format`` - mirroring how most image-generation APIs (including
    OpenAI's) let the caller choose the response shape.
    """
    provider: str
    model: str
    images: list[str] = Field(default_factory=list)
    format: Literal["url", "b64_json"] = "url"
    metadata: dict = Field(default_factory=dict)
