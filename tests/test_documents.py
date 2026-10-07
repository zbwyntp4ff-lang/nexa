"""Tests for the document processing subsystem (TXT/CSV/JSON/PDF/DOCX)."""
from __future__ import annotations
import io
import json
import pytest
from app.documents.processor import DocumentProcessor, build_default_document_processor
from app.models.errors import DocumentParsingError, DocumentTooLargeError, UnsupportedDocumentFormatError
@pytest.fixture
def processor() -> DocumentProcessor:
    return build_default_document_processor()
# --- TXT -----------------------------------------------------------------------
def test_txt_parser_extracts_text(processor: DocumentProcessor):
    result = processor.process("Hello, NEXA!".encode("utf-8"), "note.txt")
    assert result.format == "txt"
    assert result.text == "Hello, NEXA!"
    assert result.metadata["char_count"] == len("Hello, NEXA!")
def test_txt_parser_handles_invalid_utf8_gracefully(processor: DocumentProcessor):
    result = processor.process(b"\xff\xfe not quite utf8", "broken.txt")
    assert result.format == "txt"
    assert isinstance(result.text, str)
# --- CSV -----------------------------------------------------------------------
def test_csv_parser_extracts_rows(processor: DocumentProcessor):
    csv_bytes = b"name,age\nAlice,30\nBob,25\n"
    result = processor.process(csv_bytes, "people.csv")
    assert result.format == "csv"
    assert result.metadata["row_count"] == 2
    assert result.metadata["header"] == ["name", "age"]
    assert "Alice" in result.text
    assert "Bob" in result.text
def test_csv_parser_handles_empty_file(processor: DocumentProcessor):
    result = processor.process(b"", "empty.csv")
    assert result.metadata["row_count"] == 0
# --- JSON -----------------------------------------------------------------------
def test_json_parser_extracts_structured_text(processor: DocumentProcessor):
    data = {"name": "NEXA", "version": 3}
    result = processor.process(json.dumps(data).encode("utf-8"), "config.json")
    assert result.format == "json"
    assert result.metadata["type"] == "dict"
    parsed_back = json.loads(result.text)
    assert parsed_back == data
def test_json_parser_rejects_invalid_json(processor: DocumentProcessor):
    with pytest.raises(DocumentParsingError):
        processor.process(b"{not valid json", "broken.json")
def test_json_parser_handles_list_payload(processor: DocumentProcessor):
    data = [1, 2, 3]
    result = processor.process(json.dumps(data).encode("utf-8"), "list.json")
    assert result.metadata["type"] == "list"
    assert result.metadata["item_count"] == 3
# --- PDF -----------------------------------------------------------------------
def _make_test_pdf_bytes(text: str) -> bytes:
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # pypdf's PdfWriter doesn't offer high-level text drawing without extra
    # deps, so we validate the pipeline structurally (page_count) here and
    # rely on a real-world PDF fixture-free smoke test for extraction.
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
def test_pdf_parser_reports_page_count(processor: DocumentProcessor):
    pdf_bytes = _make_test_pdf_bytes("hello")
    result = processor.process(pdf_bytes, "doc.pdf")
    assert result.format == "pdf"
    assert result.metadata["page_count"] == 1
def test_pdf_parser_rejects_corrupt_pdf(processor: DocumentProcessor):
    with pytest.raises(DocumentParsingError):
        processor.process(b"not a real pdf file", "broken.pdf")
# --- DOCX -----------------------------------------------------------------------
def _make_test_docx_bytes(paragraphs: list[str]) -> bytes:
    import docx
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
def test_docx_parser_extracts_paragraphs(processor: DocumentProcessor):
    docx_bytes = _make_test_docx_bytes(["First paragraph.", "Second paragraph."])
    result = processor.process(docx_bytes, "doc.docx")
    assert result.format == "docx"
    assert "First paragraph." in result.text
    assert "Second paragraph." in result.text
    assert result.metadata["paragraph_count"] == 2
def test_docx_parser_rejects_corrupt_docx(processor: DocumentProcessor):
    with pytest.raises(DocumentParsingError):
        processor.process(b"not a real docx file", "broken.docx")
# --- DocumentProcessor dispatch / limits -----------------------------------------
def test_processor_rejects_unsupported_format(processor: DocumentProcessor):
    with pytest.raises(UnsupportedDocumentFormatError):
        processor.process(b"whatever", "file.exe")
def test_processor_rejects_file_without_extension(processor: DocumentProcessor):
    with pytest.raises(UnsupportedDocumentFormatError):
        processor.process(b"whatever", "no_extension")
def test_processor_enforces_max_size():
    small_processor = DocumentProcessor(max_size_bytes=10)
    from app.documents.txt_parser import TxtParser
    small_processor.register(TxtParser())
    with pytest.raises(DocumentTooLargeError):
        small_processor.process(b"x" * 100, "big.txt")
def test_processor_supported_formats_lists_all_five(processor: DocumentProcessor):
    formats = processor.supported_formats()
    for fmt in ("txt", "csv", "json", "pdf", "docx"):
        assert fmt in formats
# --- XLSX (Part 8) --------------------------------------------------------------
def _make_test_xlsx_bytes(rows: list[list[object]]) -> bytes:
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()
def test_xlsx_parser_extracts_rows(processor: DocumentProcessor):
    xlsx_bytes = _make_test_xlsx_bytes([["name", "age"], ["Alice", 30], ["Bob", 25]])
    result = processor.process(xlsx_bytes, "people.xlsx")
    assert result.format == "xlsx"
    assert result.metadata["sheet_count"] == 1
    assert result.metadata["row_count"] == 3
    assert "Alice" in result.text
    assert "Bob" in result.text
def test_xlsx_parser_rejects_corrupt_xlsx(processor: DocumentProcessor):
    with pytest.raises(DocumentParsingError):
        processor.process(b"not a real xlsx file", "broken.xlsx")
# --- Page limits and text truncation (Part 8) -----------------------------------
def test_processor_enforces_max_pages():
    from app.documents.pdf_parser import PdfParser
    small_processor = DocumentProcessor(max_size_bytes=10_000_000, max_pages=1)
    small_processor.register(PdfParser())
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(DocumentTooLargeError):
        small_processor.process(buf.getvalue(), "two_pages.pdf")
def test_processor_truncates_text_over_max_chars():
    from app.documents.txt_parser import TxtParser
    small_processor = DocumentProcessor(max_size_bytes=10_000_000, max_text_chars=10)
    small_processor.register(TxtParser())
    result = small_processor.process(b"0123456789ABCDEF", "long.txt")
    assert result.text == "0123456789"
    assert result.metadata["truncated"] is True
    assert result.metadata["original_char_count"] == 16
def test_processor_never_executes_document_content(processor: DocumentProcessor):
    # A txt "document" containing code must come back as inert text, never
    # be executed - this is a documentation-style safety check.
    payload = b"import os\nos.system('rm -rf /')\n"
    result = processor.process(payload, "dangerous.txt")
    assert result.text == payload.decode("utf-8")
