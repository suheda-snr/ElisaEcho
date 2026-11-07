"""Deterministic stand-in for Gemini embeddings (no API calls).

Bag-of-words hashing into 768 dimensions with crude stemming: texts sharing words get
similar vectors, which is enough to test vector retrieval end to end.
"""

import math
import re
import zlib

from app.ai.gemini import GeminiUnavailableError
from app.models import EMBEDDING_DIMENSION

_STOP = {"the", "and", "for", "but", "not", "with", "after", "did", "this", "that", "keeps", "was"}


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def fake_vector(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) > 2 and word not in _STOP:
            vector[zlib.crc32(_stem(word).encode()) % EMBEDDING_DIMENSION] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeEmbedder:
    model = "fake-embedding"
    dimension = EMBEDDING_DIMENSION

    def __init__(self, *, fail: bool = False, configured: bool = True) -> None:
        self.fail = fail
        self.configured = configured
        self.document_calls: list[str] = []
        self.query_calls: list[str] = []

    async def embed_document(self, text: str, title: str | None = None) -> list[float]:
        self.document_calls.append(text)
        if self.fail:
            raise GeminiUnavailableError("Gemini is temporarily unavailable (HTTP 503).")
        return fake_vector(text)

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        if self.fail:
            raise GeminiUnavailableError("Gemini is temporarily unavailable (HTTP 503).")
        return fake_vector(text)
