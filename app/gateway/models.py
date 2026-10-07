"""Data models for the Model Gateway.
Capability tags describe which task kinds a model is configured to accept.
They are a routing table, not a quality score, and they do not mean one
model is objectively better than another.
"""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
class TaskKind(str, Enum):
    SIMPLE = "simple"
    REASONING = "reasoning"
    CODING = "coding"
    RESEARCH = "research"
    LOCAL = "local"
class ModelCard(BaseModel):
    """Registry entry for one model. Never contains credentials."""
    provider: str
    model_id: str
    display_name: str
    capabilities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True
    availability: str = "unknown"
    availability_reason: str | None = None
class Selection(BaseModel):
    """The user's current provider/model choice. ``auto`` lets the policy decide."""
    mode: str = "manual"
    provider: str | None = None
    model_id: str | None = None
    allow_fallback: bool = False
class GatewayResult(BaseModel):
    """What the gateway returns after a model actually handled the request."""
    text: str
    provider: str
    model_id: str
    display_name: str
    fallback_used: bool = False
    fallback_from: str | None = None
class StreamEvent(BaseModel):
    type: str
    text: str = ""
    provider: str | None = None
    model: str | None = None
    display_name: str | None = None
    fallback_used: bool = False
    fallback_from: str | None = None
    error: str | None = None
    message: str | None = None
    #: Knowledge Base sources actually used, attached to the final "done"
    #: event by NexaCore (Part 9) - ModelGateway itself knows nothing about
    #: the Knowledge Base.
    citations: list[dict] = Field(default_factory=list)
    #: Latency diagnostics (milliseconds). Populated on meta/done events.
    ttft_ms: float | None = None
    total_ms: float | None = None
    backend_received_ms: float | None = None
    provider_start_ms: float | None = None
