"""Data models for the NEXA vision subsystem."""
from __future__ import annotations
from pydantic import BaseModel, Field
class VisionAnalysisResult(BaseModel):
    """Structured output of analyzing one image."""
    description: str
    provider: str
    model: str
    tags: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)
