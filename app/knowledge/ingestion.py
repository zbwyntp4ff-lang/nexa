"""``DocumentIngestion`` (Part 9).
Pipeline: validate source/type/size -> extract text (reusing
:mod:`app.documents`) -> chunk -> embed -> store, with metadata linking each
chunk back to its document. Deduplicates by content hash so the same
document is never re-indexed twice for the same scope.
Security: desktop-folder ingestion goes through the *same*
:func:`app.tools.sandbox.resolve_safe_path` the Desktop Agent's file tools
use (path traversal protection is inherited, not reimplemented). Web-result
ingestion never fetches a URL itself - it only accepts text a caller already
fetched through the SSRF-protected :mod:`app.web` pipeline. Document text is
always treated as data: chunk content is redacted for secret-shaped
substrings before it is embedded or stored, and nothing here ever executes,
evaluates, or shells out to it.
"""
from __future__ import annotations
import asyncio
import hashlib
from pathlib import Path
from app.core.logging_config import get_logger
from app.core.secrets import redact_secrets
from app.documents.processor import DocumentProcessor
from app.knowledge.chunker import DocumentChunker
from app.knowledge.document_store import DocumentStore
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSourceType, KnowledgeStatus
from app.knowledge.vector_store import VectorStore
from app.models.errors import (
    DocumentParsingError,
    DocumentTooLargeError,
    KnowledgeIndexingTimeoutError,
    KnowledgeSourceNotAllowedError,
    UnsupportedDocumentFormatError,
)
from app.tools.sandbox import resolve_safe_path
logger = get_logger("nexa.knowledge.ingestion")
class DocumentIngestion:
    def __init__(
        self,
        document_processor: DocumentProcessor,
        chunker: DocumentChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        document_store: DocumentStore,
        *,
        max_size_bytes: int,
        indexing_timeout_seconds: float,
        desktop_sandbox_root: Path,
    ) -> None:
        self._processor = document_processor
        self._chunker = chunker
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._documents = document_store
        self._max_size_bytes = max_size_bytes
        self._timeout = indexing_timeout_seconds
        self._desktop_sandbox_root = desktop_sandbox_root
    async def ingest_upload(
        self, filename: str, raw: bytes, *, project_id: str | None = None, conversation_id: str | None = None
    ) -> KnowledgeDocument:
        return await self._ingest_bytes(
            filename=filename,
            raw=raw,
            source_type=KnowledgeSourceType.UPLOAD,
            source=filename,
            project_id=project_id,
            conversation_id=conversation_id,
        )
    async def ingest_desktop_file(
        self, relative_path: str, *, project_id: str | None = None, conversation_id: str | None = None
    ) -> KnowledgeDocument:
        """Ingest a file from the Desktop Agent's sandboxed workspace only.
        Raises:
            app.models.errors.PathTraversalError: If ``relative_path`` escapes the sandbox.
            app.models.errors.KnowledgeSourceNotAllowedError: If the file doesn't exist.
        """
        safe_path = resolve_safe_path(self._desktop_sandbox_root, relative_path)
        if not safe_path.is_file():
            raise KnowledgeSourceNotAllowedError(
                f"'{relative_path}' was not found in the Desktop Agent's allowed workspace."
            )
        raw = safe_path.read_bytes()
        return await self._ingest_bytes(
            filename=safe_path.name,
            raw=raw,
            source_type=KnowledgeSourceType.DESKTOP_FILE,
            source=relative_path,
            project_id=project_id,
            conversation_id=conversation_id,
        )
    async def ingest_web_result(
        self, url: str, title: str, text: str, *, project_id: str | None = None, conversation_id: str | None = None
    ) -> KnowledgeDocument:
        """Ingest text already fetched by the SSRF-protected web pipeline (never fetches itself)."""
        return await self._ingest_text(
            text=text,
            filename=title or url,
            source_type=KnowledgeSourceType.WEB_RESEARCH,
            source=url,
            format_="web",
            project_id=project_id,
            conversation_id=conversation_id,
        )
    async def ingest_note(
        self, title: str, text: str, *, project_id: str | None = None, conversation_id: str | None = None
    ) -> KnowledgeDocument:
        return await self._ingest_text(
            text=text,
            filename=title,
            source_type=KnowledgeSourceType.NOTE,
            source=title,
            format_="note",
            project_id=project_id,
            conversation_id=conversation_id,
        )
    # --- shared pipeline -----------------------------------------------------
    def _extension(self, filename: str) -> str:
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    async def _ingest_bytes(
        self,
        *,
        filename: str,
        raw: bytes,
        source_type: KnowledgeSourceType,
        source: str,
        project_id: str | None,
        conversation_id: str | None,
    ) -> KnowledgeDocument:
        if len(raw) > self._max_size_bytes:
            raise DocumentTooLargeError(
                f"'{filename}' is {len(raw)} bytes, exceeding the maximum of {self._max_size_bytes} bytes."
            )
        extension = self._extension(filename)
        if extension not in self._processor.supported_formats():
            raise UnsupportedDocumentFormatError(extension or "(none)", available=self._processor.supported_formats())
        doc_hash = hashlib.sha256(raw).hexdigest()
        existing = self._documents.find_by_hash(doc_hash, project_id, conversation_id)
        if existing is not None:
            logger.info("document_ingestion_completed document_id=%s dedup=true", existing.id)
            return existing
        document = KnowledgeDocument(
            filename=filename,
            source_type=source_type,
            source=source,
            format=extension,
            size_bytes=len(raw),
            status=KnowledgeStatus.PROCESSING,
            project_id=project_id,
            conversation_id=conversation_id,
            doc_hash=doc_hash,
        )
        self._documents.save(document)
        logger.info("document_ingestion_started document_id=%s source_type=%s", document.id, source_type.value)
        try:
            loop = asyncio.get_running_loop()
            parsed = await asyncio.wait_for(
                loop.run_in_executor(None, self._processor.process, raw, filename),
                timeout=self._timeout,
            )
        except (DocumentTooLargeError, UnsupportedDocumentFormatError, DocumentParsingError) as exc:
            self._fail(document, exc.message)
            return document
        except TimeoutError:
            self._fail(document, KnowledgeIndexingTimeoutError().message)
            return document
        self._finish(document, parsed.text)
        return document
    async def _ingest_text(
        self,
        *,
        text: str,
        filename: str,
        source_type: KnowledgeSourceType,
        source: str,
        format_: str,
        project_id: str | None,
        conversation_id: str | None,
    ) -> KnowledgeDocument:
        raw = text.encode("utf-8")
        if len(raw) > self._max_size_bytes:
            raise DocumentTooLargeError(
                f"'{filename}' is {len(raw)} bytes, exceeding the maximum of {self._max_size_bytes} bytes."
            )
        doc_hash = hashlib.sha256(raw).hexdigest()
        existing = self._documents.find_by_hash(doc_hash, project_id, conversation_id)
        if existing is not None:
            logger.info("document_ingestion_completed document_id=%s dedup=true", existing.id)
            return existing
        document = KnowledgeDocument(
            filename=filename,
            source_type=source_type,
            source=source,
            format=format_,
            size_bytes=len(raw),
            status=KnowledgeStatus.PROCESSING,
            project_id=project_id,
            conversation_id=conversation_id,
            doc_hash=doc_hash,
        )
        self._documents.save(document)
        logger.info("document_ingestion_started document_id=%s source_type=%s", document.id, source_type.value)
        self._finish(document, text)
        return document
    def _finish(self, document: KnowledgeDocument, text: str) -> None:
        """Chunk, embed, and store - text is always treated as data, never
        as instructions (nothing here interprets or executes it)."""
        pieces = self._chunker.split(text)
        if not pieces:
            self._fail(document, "No extractable text was found in this document.")
            return
        chunks = []
        for index, piece in enumerate(pieces):
            safe_text = redact_secrets(piece)
            vector = self._embeddings.embed(safe_text)
            chunks.append(
                KnowledgeChunk(
                    document_id=document.id,
                    text=safe_text,
                    embedding=vector,
                    chunk_index=index,
                    project_id=document.project_id,
                    conversation_id=document.conversation_id,
                )
            )
        self._vector_store.add_chunks(chunks)
        document.status = KnowledgeStatus.READY
        document.chunk_count = len(chunks)
        self._documents.save(document)
        logger.info("document_ingestion_completed document_id=%s chunks=%d", document.id, len(chunks))
    def _fail(self, document: KnowledgeDocument, message: str) -> None:
        document.status = KnowledgeStatus.ERROR
        document.error = message
        self._documents.save(document)
        logger.warning("document_ingestion_failed document_id=%s error=%s", document.id, message)
