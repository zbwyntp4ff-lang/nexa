"""Tracks the set of page documents collected during a research session.
Deduplicates by URL and by content hash (two different URLs sometimes serve
identical content, e.g. mirrors or tracking-parameter variants).
"""
from __future__ import annotations
from app.web.models import PageDocument
class SourceManager:
    def __init__(self) -> None:
        self._by_url: dict[str, PageDocument] = {}
        self._seen_hashes: set[str] = set()
    def add(self, document: PageDocument) -> bool:
        """Add ``document`` if it is not a duplicate. Returns ``True`` if added."""
        if document.url in self._by_url:
            return False
        if document.content_hash in self._seen_hashes:
            return False
        self._by_url[document.url] = document
        self._seen_hashes.add(document.content_hash)
        return True
    def get_all(self) -> list[PageDocument]:
        return list(self._by_url.values())
    def get(self, url: str) -> PageDocument | None:
        return self._by_url.get(url)
    def clear(self) -> None:
        self._by_url.clear()
        self._seen_hashes.clear()
    def __len__(self) -> int:
        return len(self._by_url)
