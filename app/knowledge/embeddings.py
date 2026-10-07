"""``EmbeddingProvider`` interface + local implementation (Part 9).
``LocalEmbeddingProvider`` is a dependency-free, fully offline embedding:
a deterministic hashing-trick bag-of-words vector (stable across processes
via ``hashlib``, unlike Python's salted ``hash()``). It is intentionally
simple - swapping in a real embedding model or a remote API later only
means implementing this same interface, per Part 9's "replaceable
components" requirement. No paid external service is required to use
NEXA's Knowledge Base.
"""
from __future__ import annotations
import hashlib
import math
import re
from abc import ABC, abstractmethod
_WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)
DEFAULT_DIMENSIONS = 256
class EmbeddingProvider(ABC):
    """Abstract interface: text in, a fixed-length float vector out."""
    name: str = "base"
    dimensions: int
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a normalized embedding vector for ``text``."""
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _WORD_PATTERN.findall(text) if len(token) > 1]
def _stable_hash(token: str) -> int:
    # hashlib is stable across processes/runs, unlike Python's str hash()
    # (salted per-process for security) - required for reproducible vectors.
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
class LocalEmbeddingProvider(EmbeddingProvider):
    """Hashing-trick bag-of-words embedding - offline, deterministic, free."""
    name = "local"
    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS) -> None:
        self.dimensions = dimensions
    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = _tokenize(text)
        for token in tokens:
            digest = _stable_hash(token)
            index = digest % self.dimensions
            sign = 1.0 if (digest >> 1) % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    # Both vectors are already normalized by LocalEmbeddingProvider, but
    # guard against future providers that don't normalize.
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
class EmbeddingProviderFactory:
    """Selects an :class:`EmbeddingProvider`. Only ``local`` is implemented today.
    A future remote provider (e.g. an API-based embedding model) would be
    added here the same way :class:`app.providers.factory.ProviderFactory`
    adds AI providers - never called unless explicitly configured, and never
    required for the Knowledge Base to work locally.
    """
    @staticmethod
    def create(name: str = "local", dimensions: int = DEFAULT_DIMENSIONS) -> EmbeddingProvider:
        if name == "local":
            return LocalEmbeddingProvider(dimensions=dimensions)
        raise ValueError(f"Unknown embedding provider '{name}'. Available: local.")
