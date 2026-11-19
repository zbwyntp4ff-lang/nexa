"""Tests for the multimodal attachment pipeline (Part 8).
Upload -> Validation -> Parsing -> Extraction -> Chunking -> Context ->
Model -> Response. No real API keys are used; provider calls are exercised
through :class:`ScriptedProvider`-style stand-ins registered directly on a
:class:`app.gateway.gateway.ModelGateway`, mirroring ``test_model_gateway.py``.
"""
from __future__ import annotations
import asyncio
import base64
import io
import json
import logging
import time
from collections.abc import AsyncIterator
import pytest
from app.agent.agent import Agent
from app.agent.executor import Executor
from app.agent.planner import RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.attachments.manager import AttachmentManager
from app.attachments.models import AttachmentKind, AttachmentStatus
from app.attachments.validation import safe_extension, validate_upload, verify_signature
from app.config.settings import Settings
from app.core.logging_config import SecretRedactionFilter
from app.core.nexa_core import NexaCore
from app.documents.processor import build_default_document_processor
from app.gateway.catalog import static_catalog
from app.gateway.errors import AUTHENTICATION_ERROR, GatewayError
from app.gateway.gateway import ModelGateway
from app.gateway.model_registry import ModelRegistry
from app.gateway.provider_registry import ProviderRegistry
from app.models.chat import ChatMessage, ChatRequest, ChatRole
from app.models.errors import (
    AttachmentNotFoundError,
    AttachmentTooLargeError,
    AttachmentValidationError,
    ModelCapabilityError,
    TooManyAttachmentsError,
    TooManyConcurrentJobsError,
    UnsupportedAttachmentFormatError,
)
from app.orchestrator.agents import make_agent
from app.orchestrator.models import WorkflowTask
from app.orchestrator.orchestrator import Orchestrator
from app.providers.base import AIProvider
from app.providers.mock import MockProvider
from app.tools.base import Tool, ToolResult
from app.tools.calculator import CalculatorTool
from app.tools.registry import ToolRegistry
SECRET = "sk-testsecretkey1234567890"
# A real, valid 1x1 transparent PNG (well-known minimal fixture).
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
_WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8
_GIF_BYTES = b"GIF89a" + b"\x00" * 10
def _make_pdf_bytes() -> bytes:
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    import docx
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
def _make_xlsx_bytes(rows: list[list[object]]) -> bytes:
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()
def _manager(tmp_path, **overrides) -> AttachmentManager:
    max_size_bytes = overrides.pop("max_size_bytes", 10_000_000)
    max_pages = overrides.pop("max_pages", 200)
    max_text_chars = overrides.pop("max_text_chars", 200_000)
    defaults = dict(
        storage_dir=tmp_path / "attachments_tmp",
        document_processor=build_default_document_processor(
            max_size_bytes=max_size_bytes,
            max_pages=max_pages,
            max_text_chars=max_text_chars,
        ),
        max_size_bytes=max_size_bytes,
        max_attachments_per_message=5,
        processing_timeout_seconds=5.0,
        max_concurrent_jobs=4,
        ttl_seconds=3600.0,
        context_max_chars=6_000,
    )
    defaults.update(overrides)
    return AttachmentManager(**defaults)
# --- Validation ----------------------------------------------------------------
def test_safe_extension_ignores_path_traversal_in_filename():
    assert safe_extension("../../etc/passwd.txt") == "txt"
    assert safe_extension("..\\..\\windows\\evil.exe") == "exe"
    assert safe_extension("no_extension") == ""
def test_verify_signature_accepts_real_png_and_rejects_mismatch():
    assert verify_signature("png", _PNG_BYTES) is True
    assert verify_signature("png", b"not a real png") is False
    assert verify_signature("pdf", _make_pdf_bytes()) is True
    assert verify_signature("pdf", b"not a pdf") is False
def test_validate_upload_accepts_real_image():
    extension, kind, mime = validate_upload("photo.png", _PNG_BYTES, max_size_bytes=10_000_000)
    assert extension == "png"
    assert kind == AttachmentKind.IMAGE
    assert mime == "image/png"
def test_validate_upload_rejects_invalid_image_signature():
    """A renamed non-image file must not be accepted as an image (MIME-confusion defense)."""
    fake_png = b"MZ\x90\x00this-is-actually-an-executable"
    with pytest.raises(AttachmentValidationError):
        validate_upload("totally-a-photo.png", fake_png, max_size_bytes=10_000_000)
def test_validate_upload_rejects_oversized_file():
    with pytest.raises(AttachmentTooLargeError):
        validate_upload("big.txt", b"x" * 1000, max_size_bytes=100)
def test_validate_upload_rejects_unsupported_format():
    with pytest.raises(UnsupportedAttachmentFormatError):
        validate_upload("virus.exe", b"MZ\x90\x00", max_size_bytes=10_000_000)
def test_validate_upload_rejects_empty_file():
    with pytest.raises(AttachmentValidationError):
        validate_upload("empty.txt", b"", max_size_bytes=10_000_000)
# --- AttachmentManager: upload pipeline -----------------------------------------
async def test_upload_image_is_ready_without_parsing(tmp_path):
    manager = _manager(tmp_path)
    record = await manager.upload("photo.png", _PNG_BYTES)
    assert record.status == AttachmentStatus.READY
    assert record.kind == AttachmentKind.IMAGE
    assert record.char_count is None
async def test_upload_document_extracts_and_chunks(tmp_path):
    manager = _manager(tmp_path)
    record = await manager.upload("notes.txt", b"Hello NEXA. " * 50)
    assert record.status == AttachmentStatus.READY
    assert record.kind == AttachmentKind.DOCUMENT
    assert record.char_count == len(b"Hello NEXA. " * 50)
    assert record.chunk_count is not None and record.chunk_count >= 1
    assert record.text_preview and "Hello NEXA" in record.text_preview
async def test_upload_pdf_docx_csv_xlsx(tmp_path):
    manager = _manager(tmp_path)
    pdf_record = await manager.upload("doc.pdf", _make_pdf_bytes())
    assert pdf_record.status == AttachmentStatus.READY
    assert pdf_record.page_count == 1
    docx_record = await manager.upload("doc.docx", _make_docx_bytes(["Hello from docx."]))
    assert docx_record.status == AttachmentStatus.READY
    assert "Hello from docx." in manager.get_text(docx_record.id)
    csv_record = await manager.upload("data.csv", b"name,age\nAlice,30\n")
    assert csv_record.status == AttachmentStatus.READY
    assert "Alice" in manager.get_text(csv_record.id)
    xlsx_record = await manager.upload("data.xlsx", _make_xlsx_bytes([["name", "age"], ["Bob", 25]]))
    assert xlsx_record.status == AttachmentStatus.READY
    assert "Bob" in manager.get_text(xlsx_record.id)
async def test_upload_rejects_unsupported_format(tmp_path):
    manager = _manager(tmp_path)
    with pytest.raises(UnsupportedAttachmentFormatError):
        await manager.upload("virus.exe", b"MZ\x90\x00binary")
async def test_upload_rejects_invalid_image(tmp_path):
    manager = _manager(tmp_path)
    with pytest.raises(AttachmentValidationError):
        await manager.upload("fake.png", b"not actually a png")
async def test_upload_rejects_oversized_file(tmp_path):
    manager = _manager(tmp_path, max_size_bytes=100)
    with pytest.raises(AttachmentTooLargeError):
        await manager.upload("big.txt", b"x" * 1000)
async def test_upload_marks_failed_on_corrupt_but_correctly_signed_pdf(tmp_path):
    """A valid-looking PDF header that pypdf can't actually parse -> FAILED record, not raised."""
    manager = _manager(tmp_path)
    corrupt_pdf = b"%PDF-1.4\ncorrupt garbage that is not a real xref table"
    record = await manager.upload("broken.pdf", corrupt_pdf)
    assert record.status == AttachmentStatus.FAILED
    assert record.error
async def test_upload_never_persists_temp_file_for_documents(tmp_path):
    """Documents: the temp file is deleted immediately after text extraction."""
    manager = _manager(tmp_path)
    record = await manager.upload("notes.txt", b"secret plans")
    storage_dir = tmp_path / "attachments_tmp"
    remaining = list(storage_dir.glob(f"{record.id}.*"))
    assert remaining == []
async def test_upload_keeps_temp_file_for_images_until_deleted(tmp_path):
    manager = _manager(tmp_path)
    record = await manager.upload("photo.png", _PNG_BYTES)
    storage_dir = tmp_path / "attachments_tmp"
    assert list(storage_dir.glob(f"{record.id}.*"))
    manager.delete(record.id)
    assert list(storage_dir.glob(f"{record.id}.*")) == []
# --- Retrieval / deletion / not found -------------------------------------------
async def test_get_and_delete_attachment(tmp_path):
    manager = _manager(tmp_path)
    record = await manager.upload("notes.txt", b"hello")
    fetched = manager.get(record.id)
    assert fetched.id == record.id
    manager.delete(record.id)
    with pytest.raises(AttachmentNotFoundError):
        manager.get(record.id)
async def test_document_retrieval_returns_bounded_text(tmp_path):
    manager = _manager(tmp_path, max_text_chars=20)
    record = await manager.upload("long.txt", b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert record.truncated is True
    text = manager.get_text(record.id)
    assert len(text) == 20
def test_get_unknown_attachment_raises_not_found(tmp_path):
    manager = _manager(tmp_path)
    with pytest.raises(AttachmentNotFoundError):
        manager.get("does-not-exist")
# --- Cleanup / TTL ---------------------------------------------------------------
async def test_cleanup_expired_removes_record_and_temp_file(tmp_path, monkeypatch):
    manager = _manager(tmp_path, ttl_seconds=0.01)
    record = await manager.upload("photo.png", _PNG_BYTES)
    storage_dir = tmp_path / "attachments_tmp"
    assert list(storage_dir.glob(f"{record.id}.*"))
    real_now = time.time()
    monkeypatch.setattr(time, "time", lambda: real_now + 100_000)
    removed = manager.cleanup_expired()
    assert removed == 1
    assert list(storage_dir.glob(f"{record.id}.*")) == []
    with pytest.raises(AttachmentNotFoundError):
        manager.get(record.id)
# --- Timeout ---------------------------------------------------------------------
async def test_processing_timeout_marks_failed(tmp_path, monkeypatch):
    manager = _manager(tmp_path, max_text_chars=200_000)
    manager._timeout = 0.01  # noqa: SLF001 - directly tighten the timeout for this test
    def _slow_process(raw: bytes, filename: str):
        time.sleep(0.2)
        raise AssertionError("should have been cancelled by the timeout")
    monkeypatch.setattr(manager._processor, "process", _slow_process)  # noqa: SLF001
    record = await manager.upload("slow.txt", b"hello world")
    assert record.status == AttachmentStatus.FAILED
    assert "timed out" in (record.error or "").lower()
# --- Concurrency limit -------------------------------------------------------------
async def test_too_many_concurrent_jobs_raises(tmp_path, monkeypatch):
    manager = _manager(tmp_path, max_concurrent_jobs=1)
    def _slow_process(raw: bytes, filename: str):
        time.sleep(0.05)
        return build_default_document_processor().process(raw, filename)
    monkeypatch.setattr(manager._processor, "process", _slow_process)  # noqa: SLF001
    results = await asyncio.gather(
        manager.upload("a.txt", b"first document"),
        manager.upload("b.txt", b"second document"),
        return_exceptions=True,
    )
    outcomes = [type(r) for r in results]
    assert TooManyConcurrentJobsError in outcomes
# --- Context building (chunking + retrieval) --------------------------------------
async def test_document_context_is_bounded_and_only_from_documents(tmp_path):
    manager = _manager(tmp_path)
    doc = await manager.upload("notes.txt", b"NEXA gateway routes chat requests to providers. " * 100)
    image = await manager.upload("photo.png", _PNG_BYTES)
    context = manager.document_context([doc.id, image.id], query="gateway routes", max_chars=200)
    assert len(context) <= 200
    assert "notes.txt" in context
    assert "photo.png" not in context
async def test_document_context_skips_unready_or_missing_ids(tmp_path):
    manager = _manager(tmp_path)
    assert manager.document_context(["missing-id"], query="anything") == ""
# --- Security: secrets never appear in logs -------------------------------------
async def test_attachment_content_and_filenames_with_secrets_never_logged(tmp_path, caplog):
    manager = _manager(tmp_path)
    secret_text = f"my api key is {SECRET}".encode()
    with caplog.at_level(logging.INFO):
        record = await manager.upload("notes.txt", secret_text)
    assert record.status == AttachmentStatus.READY
    assert SECRET not in caplog.text
    log_record = logging.LogRecord(
        name="nexa.attachments", level=logging.INFO, pathname=__file__, lineno=1,
        msg="attachment content: %s", args=(secret_text.decode(),), exc_info=None,
    )
    SecretRedactionFilter().filter(log_record)
    assert SECRET not in str(log_record.args)
# --- Vision capability enforcement (ModelGateway) --------------------------------
class _ScriptedProvider(AIProvider):
    def __init__(self, name: str, model: str, text: str = "ok") -> None:
        self.name = name
        self._model = model
        self._text = text
        self.received_images: list = []
        self.received_messages: list = []
    @property
    def model_name(self) -> str:
        return self._model
    async def generate(self, messages):
        self.received_messages = list(messages)
        last_user = next((m for m in reversed(messages) if m.role.value == "user"), None)
        if last_user:
            self.received_images = list(last_user.images)
        return self._text
    async def stream(self, messages) -> AsyncIterator[str]:
        yield self._text
    async def health_check(self) -> bool:
        return True
def _vision_gateway(**settings_kw) -> tuple[ModelGateway, dict[tuple[str, str], _ScriptedProvider]]:
    terra = _ScriptedProvider("openai", "gpt-4.1-mini", text="terra-no-vision")
    sol = _ScriptedProvider("openai", "gpt-4o", text="sol-vision")
    providers = {("openai", "gpt-4.1-mini"): terra, ("openai", "gpt-4o"): sol}
    registry = ProviderRegistry()
    for provider_name in {name for name, _model in providers}:
        registry.register(provider_name, lambda model_id, pname=provider_name: providers[(pname, model_id)])
    registry.register("mock", lambda model_id: MockProvider())
    settings_kw.setdefault("AI_PROVIDER", "mock")
    settings_kw.setdefault("OPENAI_API_KEY", "sk-not-a-real-key")
    gateway = ModelGateway(
        providers=registry,
        models=ModelRegistry(static_catalog()),
        settings=Settings(**settings_kw),
    )
    return gateway, providers
def _image_payload() -> list[tuple[bytes, str]]:
    return [(_PNG_BYTES, "image/png")]
async def test_gateway_rejects_image_for_manual_non_vision_model():
    gateway, _providers = _vision_gateway()
    gateway.set_selection("openai", "gpt-4.1-mini", False)
    with pytest.raises(ModelCapabilityError) as caught:
        await gateway.chat([ChatMessage(role=ChatRole.USER, content="what is in this image?")], images=_image_payload())
    assert "does not support image" in str(caught.value).lower()
    assert "gpt-4o" in str(caught.value).lower()
async def test_gateway_sends_image_to_manual_vision_capable_model():
    gateway, providers = _vision_gateway()
    gateway.set_selection("openai", "gpt-4o", False)
    result = await gateway.chat([ChatMessage(role=ChatRole.USER, content="describe this")], images=_image_payload())
    assert result.model_id == "gpt-4o"
    assert len(providers[("openai", "gpt-4o")].received_images) == 1
async def test_gateway_auto_picks_vision_capable_model_for_images():
    gateway, providers = _vision_gateway(MODEL_SELECTION="auto")
    result = await gateway.chat([ChatMessage(role=ChatRole.USER, content="describe this photo")], images=_image_payload())
    assert result.model_id == "gpt-4o"
    assert len(providers[("openai", "gpt-4o")].received_images) == 1
async def test_gateway_raises_when_no_model_supports_vision():
    registry = ProviderRegistry()
    registry.register("mock", lambda model_id: MockProvider())
    gateway = ModelGateway(
        providers=registry,
        models=ModelRegistry([card for card in static_catalog() if not card.supports_vision]),
        settings=Settings(AI_PROVIDER="mock"),
    )
    with pytest.raises(ModelCapabilityError):
        await gateway.chat([ChatMessage(role=ChatRole.USER, content="describe this")], images=_image_payload())
# --- NexaCore integration ---------------------------------------------------------
def _core_settings(**overrides) -> Settings:
    defaults = dict(AI_PROVIDER="mock", MAX_MESSAGE_LENGTH=4000, REQUEST_TIMEOUT_SECONDS=5.0)
    defaults.update(overrides)
    return Settings(**defaults)
async def test_chat_with_document_attachment_injects_context(tmp_path):
    manager = _manager(tmp_path)
    doc = await manager.upload("notes.txt", b"The secret ingredient is basil.")
    captured = _ScriptedProvider("mock", "nexa-mock-1", text="Basil is the answer.")
    registry = ProviderRegistry()
    registry.register("mock", lambda model_id: captured)
    gateway = ModelGateway(providers=registry, models=ModelRegistry(static_catalog()), settings=_core_settings())
    gateway.set_selection("mock", "nexa-mock-1", False)
    core = NexaCore(provider=MockProvider(), settings=_core_settings(), gateway=gateway, attachments=manager)
    response = await core.chat(ChatRequest(message="What is the secret ingredient?", attachment_ids=[doc.id]))
    assert response.attachments_used == [doc.id]
    assert response.message == "Basil is the answer."
    # The document context must have reached the provider as a system message,
    # never the raw file bypassing the pipeline.
    system_texts = " ".join(m.content for m in captured.received_messages if m.role == ChatRole.SYSTEM)
    assert "basil" in system_texts.lower()
    assert "notes.txt" in system_texts
async def test_chat_rejects_too_many_attachments(tmp_path):
    manager = _manager(tmp_path, max_attachments_per_message=1)
    doc1 = await manager.upload("a.txt", b"one")
    doc2 = await manager.upload("b.txt", b"two")
    core = NexaCore(provider=MockProvider(), settings=_core_settings(MAX_ATTACHMENTS_PER_MESSAGE=1), attachments=manager)
    with pytest.raises(TooManyAttachmentsError):
        await core.chat(ChatRequest(message="hi", attachment_ids=[doc1.id, doc2.id]))
async def test_chat_rejects_missing_attachment_id(tmp_path):
    manager = _manager(tmp_path)
    core = NexaCore(provider=MockProvider(), settings=_core_settings(), attachments=manager)
    with pytest.raises(AttachmentNotFoundError):
        await core.chat(ChatRequest(message="hi", attachment_ids=["missing"]))
async def test_chat_rejects_failed_attachment(tmp_path):
    manager = _manager(tmp_path)
    record = await manager.upload("broken.pdf", b"%PDF-1.4\ncorrupt garbage")
    assert record.status == AttachmentStatus.FAILED
    core = NexaCore(provider=MockProvider(), settings=_core_settings(), attachments=manager)
    with pytest.raises(AttachmentValidationError):
        await core.chat(ChatRequest(message="hi", attachment_ids=[record.id]))
async def test_chat_image_without_gateway_raises_capability_error(tmp_path):
    manager = _manager(tmp_path)
    image = await manager.upload("photo.png", _PNG_BYTES)
    core = NexaCore(provider=MockProvider(), settings=_core_settings(), attachments=manager)  # gateway=None
    with pytest.raises(ModelCapabilityError):
        await core.chat(ChatRequest(message="what is this?", attachment_ids=[image.id]))
async def test_chat_sends_image_through_gateway_to_vision_model(tmp_path):
    manager = _manager(tmp_path)
    image = await manager.upload("photo.png", _PNG_BYTES)
    gateway, providers = _vision_gateway()
    gateway.set_selection("openai", "gpt-4o", False)
    core = NexaCore(provider=MockProvider(), settings=_core_settings(), gateway=gateway, attachments=manager)
    response = await core.chat(ChatRequest(message="what is this?", attachment_ids=[image.id]))
    assert response.provider == "openai"
    assert len(providers[("openai", "gpt-4o")].received_images) == 1
# --- Orchestrator: least-privilege document context ------------------------------
class _StaticTool(Tool):
    name = "web_research"
    description = "Fake research tool for tests (no real network)."
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    permissions = frozenset({"network:read"})
    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="Found: NEXA is a universal AI platform. Source: example.com")
def _registry_with_research(tmp_path) -> ToolRegistry:
    from app.tools.file_read import FileReadTool
    from app.tools.file_write import FileWriteTool
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    reg.register(FileWriteTool(tmp_path))
    reg.register(FileReadTool(tmp_path))
    reg.register(_StaticTool())
    return reg
def test_document_context_only_reaches_permitted_agent_types(tmp_path):
    manager = _manager(tmp_path)
    doc_record = asyncio.run(manager.upload("notes.txt", b"Confidential project plan text."))
    orch = Orchestrator(registry=_registry_with_research(tmp_path), attachment_manager=manager)
    research_context = orch._document_context_for("research", [doc_record.id], "plan")  # noqa: SLF001
    desktop_context = orch._document_context_for("desktop", [doc_record.id], "plan")  # noqa: SLF001
    review_context = orch._document_context_for("review", [doc_record.id], "plan")  # noqa: SLF001
    assert research_context and "notes.txt" in research_context
    assert desktop_context is None
    assert review_context is None
async def test_agent_combines_tool_result_with_document_context():
    scripted = _ScriptedProvider("mock", "nexa-mock-1", text="Basil, per your notes and the web.")
    registry = ProviderRegistry()
    registry.register("mock", lambda model_id: scripted)
    gateway = ModelGateway(providers=registry, models=ModelRegistry(static_catalog()), settings=_core_settings())
    gateway.set_selection("mock", "nexa-mock-1", False)
    tools = ToolRegistry()
    tools.register(_StaticTool())
    agent = make_agent("research", tools, model_gateway=gateway, max_steps=5, timeout_seconds=5, error_limit=2)
    from app.agent.models import AgentTask
    result = await agent.run(
        AgentTask(description="Research NEXA online", context="From the user's document: basil is the secret.")
    )
    assert result.success
    assert result.final_answer == "Basil, per your notes and the web."
    assert result.provider == "mock"
async def test_workflow_with_document_attachment_reaches_research_agent(tmp_path):
    manager = _manager(tmp_path)
    doc = await manager.upload("notes.txt", b"The launch date is confidential: March 3rd.")
    scripted = _ScriptedProvider("mock", "nexa-mock-1", text="The launch date is March 3rd, per your document and the web.")
    registry = ProviderRegistry()
    registry.register("mock", lambda model_id: scripted)
    gateway = ModelGateway(providers=registry, models=ModelRegistry(static_catalog()), settings=_core_settings())
    gateway.set_selection("mock", "nexa-mock-1", False)
    orch = Orchestrator(
        registry=_registry_with_research(tmp_path),
        model_gateway=gateway,
        attachment_manager=manager,
        timeout_seconds=10,
        step_timeout_seconds=5,
    )
    task = WorkflowTask(description="Research the product launch date", attachment_ids=[doc.id])
    result = await orch.run(task)
    assert result.status.value == "completed"
    assert "March 3rd" in (result.final_answer or "")
# --- API surface -------------------------------------------------------------------
def test_attachments_api_upload_get_content_delete():
    from fastapi.testclient import TestClient
    from app.api.deps import get_attachment_manager
    from app.main import app
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/attachments",
            files={"file": ("notes.txt", b"Hello from the attachments API.", "text/plain")},
        )
        assert upload.status_code == 200
        body = upload.json()
        assert body["status"] == "ready"
        assert body["kind"] == "document"
        attachment_id = body["id"]
        fetched = client.get(f"/api/v1/attachments/{attachment_id}")
        assert fetched.status_code == 200
        content = client.get(f"/api/v1/attachments/{attachment_id}/content")
        assert content.status_code == 200
        assert "Hello from the attachments API." in content.json()["text"]
        limits = client.get("/api/v1/attachments/limits")
        assert limits.status_code == 200
        assert limits.json()["max_attachments_per_message"] >= 1
        deleted = client.delete(f"/api/v1/attachments/{attachment_id}")
        assert deleted.status_code == 200
        missing = client.get(f"/api/v1/attachments/{attachment_id}")
        assert missing.status_code == 404
    get_attachment_manager.cache_clear()
def test_attachments_api_rejects_unsupported_format():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attachments",
            files={"file": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "UnsupportedAttachmentFormatError"
def test_attachments_api_rejects_invalid_image_signature():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attachments",
            files={"file": ("photo.png", b"not really a png", "image/png")},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "AttachmentValidationError"
def test_voice_status_and_transcribe_are_honest_about_not_configured():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        status = client.get("/api/v1/voice/status")
        assert status.status_code == 200
        assert status.json() == {"stt_configured": False, "tts_configured": False}
        transcribe = client.post(
            "/api/v1/voice/transcribe",
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert transcribe.status_code == 503
        assert transcribe.json()["error"] == "ProviderConfigurationError"
        synth = client.post("/api/v1/voice/synthesize", json={"text": "hello"})
        assert synth.status_code == 503


async def test_attachment_content_isolated_between_users(tmp_path):
    manager = _manager(tmp_path)
    document = await manager.upload("private.txt", b"alice confidential content", user_id="alice")
    image = await manager.upload("private.png", _PNG_BYTES, user_id="alice")

    assert manager.get(document.id, user_id="alice").id == document.id
    with pytest.raises(AttachmentNotFoundError):
        manager.resolve_ids([document.id], user_id="bob")
    assert manager.document_context([document.id], query="confidential", user_id="bob") == ""
    assert "confidential" in manager.document_context(
        [document.id], query="confidential", user_id="alice"
    )

    assert manager.has_images([image.id], user_id="alice") is True
    assert manager.has_images([image.id], user_id="bob") is False
    assert manager.image_payloads([image.id], user_id="bob") == []
    assert len(manager.image_payloads([image.id], user_id="alice")) == 1

async def test_attachment_manifest_survives_restart_for_account_deletion(tmp_path):
    storage_dir = tmp_path / "attachments_tmp"
    manager = _manager(tmp_path)
    record = await manager.upload("photo.png", _PNG_BYTES, user_id="user-a")
    image_path = storage_dir / f"{record.id}.png"
    manifest_path = storage_dir / ".ownership.json"
    assert image_path.is_file()
    assert manifest_path.is_file()

    restarted_manager = _manager(tmp_path)
    assert restarted_manager.list(user_id="user-a") == []
    assert restarted_manager.delete_user("user-a") == 1
    assert not image_path.exists()
    assert not manifest_path.exists() or '"user-a"' not in manifest_path.read_text(encoding="utf-8")


async def test_attachment_manifest_ttl_cleanup_survives_restart(tmp_path):
    storage_dir = tmp_path / "attachments_tmp"
    manager = _manager(tmp_path, ttl_seconds=0.01)
    record = await manager.upload("photo.png", _PNG_BYTES, user_id="user-a")
    image_path = storage_dir / f"{record.id}.png"
    assert image_path.is_file()

    time.sleep(0.03)
    restarted_manager = _manager(tmp_path)
    assert restarted_manager.cleanup_expired() == 1
    assert not image_path.exists()
    assert not (storage_dir / ".ownership.json").exists() or (
        f'"{record.id}"' not in (storage_dir / ".ownership.json").read_text(encoding="utf-8")
    )


async def test_document_upload_does_not_leave_ownership_manifest_entry(tmp_path):
    manager = _manager(tmp_path)
    record = await manager.upload("notes.txt", b"private document text", user_id="user-a")
    manifest_path = tmp_path / "attachments_tmp" / ".ownership.json"
    assert record.status == AttachmentStatus.READY
    assert not manifest_path.exists() or f'"{record.id}"' not in manifest_path.read_text(encoding="utf-8")

