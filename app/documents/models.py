"""Data models for the NEXA document processing subsystem."""
from __future__ import annotations
from pydantic import BaseModel, Field
class ParsedDocument(BaseModel):
    """The structured text content extracted from an uploaded document.
    Parsing only ever *reads* the document's content - NEXA never executes,
    evaluates, or otherwise runs anything contained in an uploaded file.
    """
    filename: str
    format: str
    text: str
    metadata: dict = Field(default_factory=dict)
