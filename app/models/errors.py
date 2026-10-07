"""Domain-level exceptions used across NEXA.
These are intentionally provider/framework agnostic so that
:mod:`app.core.nexa_core` and the provider implementations can raise them
without depending on FastAPI. The API layer (``app/api``) maps them onto
appropriate HTTP responses.
"""
from __future__ import annotations
class NexaError(Exception):
    """Base class for all NEXA domain errors."""
    default_message = "An unexpected error occurred."
    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
class EmptyMessageError(NexaError):
    """Raised when the user submits an empty (or whitespace-only) message."""
    default_message = "Message must not be empty."
class MessageTooLongError(NexaError):
    """Raised when the user's message exceeds the configured length limit."""
    default_message = "Message is too long."
    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(
            f"Message length {length} exceeds the maximum of {max_length} characters."
        )
        self.length = length
        self.max_length = max_length
class UnknownProviderError(NexaError):
    """Raised when an unrecognized provider name is requested."""
    default_message = "Unknown AI provider."
    def __init__(self, provider: str, available: tuple[str, ...] = ()) -> None:
        available_str = ", ".join(available) if available else "none"
        super().__init__(
            f"Unknown AI provider '{provider}'. Available providers: {available_str}."
        )
        self.provider = provider
class ProviderConfigurationError(NexaError):
    """Raised when a provider is selected but missing required configuration."""
    default_message = "Provider is not configured correctly."
class ModelError(NexaError):
    """Raised when the underlying model/provider fails to produce a response."""
    default_message = "The model failed to generate a response."
class ProviderTimeoutError(NexaError):
    """Raised when a provider call exceeds the configured timeout."""
    default_message = "The request to the AI provider timed out."
# --- Memory (Part 2) --------------------------------------------------------
class MemoryItemNotFoundError(NexaError):
    """Raised when a requested memory item does not exist."""
    default_message = "Memory item not found."
    def __init__(self, item_id: str) -> None:
        super().__init__(f"Memory item '{item_id}' was not found.")
        self.item_id = item_id
class SecretInMemoryError(NexaError):
    """Raised when code attempts to persist a secret (API key, password, ...)."""
    default_message = (
        "Refusing to store this memory item: it looks like it contains a "
        "secret (API key, password, or token)."
    )
# --- Tools (Part 2) ----------------------------------------------------------
class ToolNotFoundError(NexaError):
    """Raised when a requested tool is not registered."""
    default_message = "Tool not found."
    def __init__(self, name: str, available: tuple[str, ...] = ()) -> None:
        available_str = ", ".join(available) if available else "none"
        super().__init__(
            f"Unknown tool '{name}'. Available tools: {available_str}."
        )
        self.name = name
class ToolAlreadyRegisteredError(NexaError):
    """Raised when attempting to register a tool name that already exists."""
    default_message = "Tool is already registered."
    def __init__(self, name: str) -> None:
        super().__init__(f"Tool '{name}' is already registered.")
        self.name = name
class ToolPermissionError(NexaError):
    """Raised when a tool call is not permitted in the current context."""
    default_message = "This tool call is not permitted."
    def __init__(self, name: str, missing: tuple[str, ...] = ()) -> None:
        missing_str = ", ".join(missing) if missing else "unspecified"
        super().__init__(
            f"Tool '{name}' requires permissions not granted: {missing_str}."
        )
        self.name = name
class ToolValidationError(NexaError):
    """Raised when tool input fails schema/validation checks."""
    default_message = "Invalid tool input."
class ToolExecutionError(NexaError):
    """Raised when a tool fails while executing."""
    default_message = "Tool execution failed."
class PathTraversalError(NexaError):
    """Raised when a filesystem tool tries to access a path outside its sandbox."""
    default_message = "Path traversal is not allowed."
    def __init__(self, path: str) -> None:
        super().__init__(f"Path '{path}' escapes the allowed workspace sandbox.")
        self.path = path
# --- Agent (Part 2) -----------------------------------------------------------
class AgentTaskError(NexaError):
    """Raised for invalid agent task input (e.g. empty description)."""
    default_message = "Invalid agent task."
# --- Web research (Part 3) ----------------------------------------------------
class InvalidURLError(NexaError):
    """Raised when a URL is malformed or uses a disallowed scheme."""
    default_message = "Invalid or unsupported URL."
class SSRFProtectionError(NexaError):
    """Raised when a URL resolves to a host that is blocked to prevent SSRF.
    Covers localhost, private/reserved/link-local networks, and non-http(s)
    schemes such as ``file://``.
    """
    default_message = "This URL is not allowed (blocked to prevent SSRF)."
class PageTooLargeError(NexaError):
    """Raised when a fetched page exceeds the configured maximum size."""
    default_message = "The page exceeds the maximum allowed size."
class WebFetchTimeoutError(NexaError):
    """Raised when fetching a page exceeds the configured timeout."""
    default_message = "Fetching the page timed out."
class WebFetchError(NexaError):
    """Raised when a page fails to be fetched for reasons other than SSRF/timeout."""
    default_message = "Failed to fetch the page."
class SearchError(NexaError):
    """Raised when a search provider fails to return results."""
    default_message = "Web search failed."
# --- Documents (Part 3) --------------------------------------------------------
class UnsupportedDocumentFormatError(NexaError):
    """Raised when a document's format has no registered parser."""
    default_message = "Unsupported document format."
    def __init__(self, format_: str, available: tuple[str, ...] = ()) -> None:
        available_str = ", ".join(available) if available else "none"
        super().__init__(
            f"Unsupported document format '{format_}'. Supported: {available_str}."
        )
        self.format = format_
class DocumentTooLargeError(NexaError):
    """Raised when a document exceeds the configured maximum size."""
    default_message = "The document exceeds the maximum allowed size."
class DocumentParsingError(NexaError):
    """Raised when a document cannot be parsed (corrupt, malformed, ...)."""
    default_message = "Failed to parse document."
# --- Attachments / multimodal input (Part 8) ---------------------------------
class AttachmentNotFoundError(NexaError):
    """Raised when a referenced attachment id does not exist (or expired)."""
    default_message = "Attachment not found."
    def __init__(self, attachment_id: str) -> None:
        super().__init__(f"Attachment '{attachment_id}' was not found (it may have expired).")
        self.attachment_id = attachment_id
class AttachmentValidationError(NexaError):
    """Raised when an uploaded file fails type/size/signature validation."""
    default_message = "The uploaded file failed validation."
class AttachmentTooLargeError(NexaError):
    """Raised when an uploaded file exceeds the configured size limit."""
    default_message = "The uploaded file is too large."
class TooManyAttachmentsError(NexaError):
    """Raised when a request includes more attachments than allowed."""
    default_message = "Too many attachments in this request."
class UnsupportedAttachmentFormatError(NexaError):
    """Raised when an uploaded file's format/extension is not on the whitelist."""
    default_message = "This file format is not supported."
    def __init__(self, format_: str, available: tuple[str, ...] = ()) -> None:
        available_str = ", ".join(available) if available else "none"
        super().__init__(
            f"Unsupported attachment format '{format_}'. Supported: {available_str}."
        )
        self.format = format_
class AttachmentProcessingTimeoutError(NexaError):
    """Raised when parsing/processing an attachment exceeds the configured timeout."""
    default_message = "Processing this attachment timed out."
class TooManyConcurrentJobsError(NexaError):
    """Raised when the concurrent attachment-processing job limit is reached."""
    default_message = "Too many attachments are being processed right now. Try again shortly."
# --- Knowledge Base / RAG (Part 9) --------------------------------------------
class KnowledgeDocumentNotFoundError(NexaError):
    """Raised when a referenced Knowledge Base document id does not exist."""
    default_message = "Knowledge Base document not found."
    def __init__(self, document_id: str) -> None:
        super().__init__(f"Knowledge Base document '{document_id}' was not found.")
        self.document_id = document_id
class KnowledgeSourceNotAllowedError(NexaError):
    """Raised when a Knowledge Base ingestion source fails a permission check
    (disallowed source type, or a desktop path outside the agent sandbox)."""
    default_message = "This source is not allowed in the Knowledge Base."
class KnowledgeIndexingTimeoutError(NexaError):
    """Raised when indexing a document exceeds the configured timeout."""
    default_message = "Indexing this document timed out."
class WorkflowNotFoundError(NexaError):
    """Raised when a workflow id does not exist."""
    default_message = "Workflow not found."
    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"Workflow '{workflow_id}' was not found.")
        self.workflow_id = workflow_id
class WorkflowStateError(NexaError):
    """Raised when a workflow action is not valid in the current status."""
    default_message = "That action is not allowed in the current workflow state."
class WorkflowInvalidTaskError(NexaError):
    """Raised when a task graph is empty, incomplete, or repeats a task."""
    default_message = "The workflow task is invalid."
class WorkflowCycleError(NexaError):
    """Raised when task dependencies contain a cycle."""
    default_message = "The workflow has a cyclic task dependency."
class WorkflowLimitError(NexaError):
    """Raised when a workflow exceeds a configured limit at creation time."""
    default_message = "The workflow exceeds a configured limit."
class WorkflowSecurityError(NexaError):
    """Raised when a workflow action would bypass an existing security rule."""
    default_message = "The workflow action was blocked by a security check."
class ModelCapabilityError(NexaError):
    """Raised when the selected model cannot handle a requested input (e.g. images).
    Normalized the same way as :class:`app.gateway.errors.GatewayError`'s
    ``invalid_request`` code (this is a client-request problem, not a
    provider transport failure), but is raised before any provider is
    called, so it never triggers a silent model swap.
    """
    default_message = "The selected model does not support this kind of input."
