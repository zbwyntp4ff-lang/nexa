"""``DocumentProcessor`` - dispatches raw file bytes to the right ``DocumentParser``."""
from __future__ import annotations
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
from app.models.errors import DocumentParsingError, DocumentTooLargeError, UnsupportedDocumentFormatError
class DocumentProcessor:
    def __init__(
        self,
        max_size_bytes: int = 10_000_000,
        max_pages: int | None = None,
        max_text_chars: int | None = None,
    ) -> None:
        self._parsers: dict[str, DocumentParser] = {}
        self._max_size_bytes = max_size_bytes
        self._max_pages = max_pages
        self._max_text_chars = max_text_chars
    def register(self, parser: DocumentParser) -> None:
        for fmt in parser.formats:
            self._parsers[fmt] = parser
    def supported_formats(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers))
    @staticmethod
    def _extension(filename: str) -> str:
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    def process(self, raw: bytes, filename: str) -> ParsedDocument:
        """Parse ``raw`` (the file's bytes) named ``filename`` into structured text.
        Raises:
            app.models.errors.DocumentTooLargeError
            app.models.errors.UnsupportedDocumentFormatError
            app.models.errors.DocumentParsingError
        """
        if len(raw) > self._max_size_bytes:
            raise DocumentTooLargeError(
                f"'{filename}' is {len(raw)} bytes, exceeding the maximum of {self._max_size_bytes} bytes."
            )
        extension = self._extension(filename)
        parser = self._parsers.get(extension)
        if parser is None:
            raise UnsupportedDocumentFormatError(extension or "(none)", available=self.supported_formats())
        try:
            parsed = parser.parse(raw, filename)
        except DocumentParsingError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize any parser crash
            raise DocumentParsingError(f"Failed to parse '{filename}': {exc}") from exc
        page_count = parsed.metadata.get("page_count")
        if self._max_pages is not None and isinstance(page_count, int) and page_count > self._max_pages:
            raise DocumentTooLargeError(
                f"'{filename}' has {page_count} pages, exceeding the maximum of {self._max_pages} pages."
            )
        if self._max_text_chars is not None and len(parsed.text) > self._max_text_chars:
            truncated_text = parsed.text[: self._max_text_chars]
            parsed = parsed.model_copy(
                update={
                    "text": truncated_text,
                    "metadata": {**parsed.metadata, "truncated": True, "original_char_count": len(parsed.text)},
                }
            )
        return parsed
def build_default_document_processor(
    max_size_bytes: int = 10_000_000,
    max_pages: int | None = None,
    max_text_chars: int | None = None,
) -> DocumentProcessor:
    """Construct a :class:`DocumentProcessor` with all built-in NEXA parsers registered."""
    from app.documents.csv_parser import CsvParser
    from app.documents.docx_parser import DocxParser
    from app.documents.json_parser import JsonParser
    from app.documents.pdf_parser import PdfParser
    from app.documents.txt_parser import TxtParser
    from app.documents.xlsx_parser import XlsxParser
    processor = DocumentProcessor(max_size_bytes=max_size_bytes, max_pages=max_pages, max_text_chars=max_text_chars)
    processor.register(TxtParser())
    processor.register(CsvParser())
    processor.register(JsonParser())
    processor.register(PdfParser())
    processor.register(DocxParser())
    processor.register(XlsxParser())
    return processor
