from __future__ import annotations

import math

import pytest

from app.knowledge.embeddings import (
    EmbeddingProviderFactory,
    LocalEmbeddingProvider,
    OllamaEmbeddingProvider,
)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_local_embedding_provider_remains_default_and_offline():
    provider = EmbeddingProviderFactory.create()
    assert isinstance(provider, LocalEmbeddingProvider)
    assert len(provider.embed("квантовая физика")) == 256


def test_ollama_embedding_provider_posts_batch_and_normalizes(monkeypatch):
    seen = {}

    def fake_post(url, *, json, timeout):
        seen.update(url=url, payload=json, timeout=timeout)
        return _Response({"embeddings": [[3, 4], [0, 2]]})

    monkeypatch.setattr("app.knowledge.embeddings.httpx.post", fake_post)
    provider = OllamaEmbeddingProvider(
        "http://127.0.0.1:11434/", "nomic-embed-text", timeout_seconds=7
    )
    result = provider.embed_batch(["квантовая физика", "линейная алгебра"])

    assert seen == {
        "url": "http://127.0.0.1:11434/api/embed",
        "payload": {
            "model": "nomic-embed-text",
            "input": ["квантовая физика", "линейная алгебра"],
        },
        "timeout": 7,
    }
    assert result == [[0.6, 0.8], [0.0, 1.0]]
    assert provider.dimensions == 2
    assert all(math.isclose(math.sqrt(sum(v * v for v in row)), 1.0) for row in result)


def test_ollama_embedding_rejects_wrong_number_of_vectors(monkeypatch):
    monkeypatch.setattr(
        "app.knowledge.embeddings.httpx.post",
        lambda *args, **kwargs: _Response({"embeddings": [[1.0]]}),
    )
    provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
    with pytest.raises(RuntimeError, match="invalid embeddings array"):
        provider.embed_batch(["first", "second"])


def test_ollama_embedding_rejects_non_finite_values(monkeypatch):
    monkeypatch.setattr(
        "app.knowledge.embeddings.httpx.post",
        lambda *args, **kwargs: _Response({"embeddings": [[float("nan")]]}),
    )
    provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
    with pytest.raises(RuntimeError, match="non-finite"):
        provider.embed("text")


def test_factory_rejects_unknown_embedding_provider():
    with pytest.raises(ValueError, match="Available: local, ollama"):
        EmbeddingProviderFactory.create(name="unknown")
