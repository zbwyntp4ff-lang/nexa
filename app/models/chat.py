"""Pydantic models used for chat interactions."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator
class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
class ImageAttachment(BaseModel):
    """One image, base64-encoded, attached to a single :class:`ChatMessage`.
    Only ever carried in-memory between the Model Gateway and a vision-capable
    provider for a single request - never persisted, never logged, and never
    sent to a model that does not declare ``supports_vision``.
    """
    data_base64: str
    mime_type: str
class ChatMessage(BaseModel):
    """A single message in a conversation."""
    role: ChatRole = ChatRole.USER
    content: str = Field(..., description="The text content of the message")
    images: list[ImageAttachment] = Field(default_factory=list)
    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("message content must not be empty")
        return value
class ChatRequest(BaseModel):
    """Incoming request body for ``POST /api/v1/chat``."""
    message: str = Field(..., description="The user's message to NEXA")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Optional prior conversation turns, oldest first",
    )
    model: str | None = Field(
        default=None,
        description="Optional model id or 'auto'. Omitted = the server selection.",
    )
    task: str | None = Field(
        default=None,
        description="Optional task kind: simple, reasoning, coding, research, local.",
    )
    attachment_ids: list[str] = Field(
        default_factory=list,
        description="Ids from POST /api/v1/attachments to include as document context or images.",
    )
    use_knowledge_base: bool = Field(
        default=False,
        description="Opt-in RAG: retrieve relevant Knowledge Base chunks and cite them in the answer.",
    )
    knowledge_project_id: str | None = Field(
        default=None, description="Scopes Knowledge Base retrieval to this project (plus global documents)."
    )
    knowledge_conversation_id: str | None = Field(
        default=None, description="Scopes Knowledge Base retrieval to this conversation (plus project/global)."
    )
    knowledge_top_k: int | None = Field(
        default=None, description="Override the configured top_k for this request."
    )
    # Server-only: stamped from the authenticated user — never trust clients.
    knowledge_user_id: str | None = Field(
        default=None,
        description="Server-only owner scope for Knowledge Base retrieval.",
    )
    request_id: str | None = Field(
        default=None,
        description="Client idempotency key for token charging (retries reuse the same id).",
    )
    apply_personalization: bool = Field(
        default=True,
        description="When false, skip profile personalization for this request only.",
    )
    project_personalization: dict | None = Field(
        default=None,
        description="Optional project overrides (style/model/language/instructions).",
    )
    # Populated by the API from the authenticated user's profile — never trust clients.
    server_personalization_hint: str | None = Field(
        default=None,
        description="Server-only compact personalization hint.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [{"message": "Привет, NEXA!"}],
        }
    }
class ChatCitation(BaseModel):
    """One Knowledge Base source actually included in the answer's context."""
    index: int
    document_id: str
    filename: str
    source: str
    page: int | None = None
    section: str | None = None
class ChatResponse(BaseModel):
    """Response body returned by ``POST /api/v1/chat``."""
    message: str
    provider: str
    model: str
    display_name: str | None = None
    fallback_used: bool = False
    fallback_from: str | None = None
    #: Auto/manual task routing label when the gateway handled the request.
    task_kind: str | None = None
    selection_mode: str | None = None
    attachments_used: list[str] = Field(default_factory=list)
    citations: list[ChatCitation] = Field(default_factory=list)
    knowledge_used: bool = False
    latency_ms: float
    #: Populated only when a provider returns verified token usage (never invented).
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
