"""Gemini text embeddings for knowledge chunks (documents) and search queries.

Stored and query vectors must come from the same model with the same dimension, so both
directions go through this one service. Vectors are L2-normalized (gemini-embedding-001
does not normalize reduced dimensions; gemini-embedding-2 does, and normalizing again is
harmless).
"""

import logging
import math
from collections import OrderedDict
from typing import Literal

from google.genai import types

from app.ai.gemini import GeminiClient, GeminiResponseError
from app.core.config import Settings
from app.models.knowledge import EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)

EmbeddingKind = Literal["document", "query"]


class EmbeddingDimensionError(GeminiResponseError):
    """The model returned a vector of the wrong size."""


def uses_text_prefixes(model: str) -> bool:
    """gemini-embedding-2 takes the task as a text prefix and rejects `task_type`."""
    return model.startswith("gemini-embedding-2")


def prepare_request(
    model: str, text: str, kind: EmbeddingKind, dimension: int, title: str | None = None
) -> tuple[str, types.EmbedContentConfig]:
    if uses_text_prefixes(model):
        content = (
            f"task: search result | query: {text}"
            if kind == "query"
            else f"title: {title or 'none'} | text: {text}"
        )
        return content, types.EmbedContentConfig(output_dimensionality=dimension)
    task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
    config = types.EmbedContentConfig(
        task_type=task,
        output_dimensionality=dimension,
        title=title if kind == "document" and title else None,
    )
    return text, config


def validate_and_normalize(values: list[float], dimension: int) -> list[float]:
    if len(values) != dimension:
        raise EmbeddingDimensionError(
            f"Embedding has {len(values)} dimensions, expected {dimension}."
        )
    norm = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingDimensionError("Embedding is empty or invalid.")
    return [v / norm for v in values]


class EmbeddingService:
    def __init__(
        self,
        gemini: GeminiClient,
        *,
        model: str,
        dimension: int = EMBEDDING_DIMENSION,
        query_cache_size: int = 256,
    ) -> None:
        self.gemini = gemini
        self.model = model
        self.dimension = dimension
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_size = query_cache_size

    @classmethod
    def from_settings(cls, settings: Settings, gemini: GeminiClient) -> "EmbeddingService":
        return cls(gemini, model=settings.gemini_embedding_model)

    @property
    def configured(self) -> bool:
        return self.gemini.configured

    async def _embed(self, text: str, kind: EmbeddingKind, title: str | None = None) -> list[float]:
        content, config = prepare_request(self.model, text, kind, self.dimension, title)
        values = await self.gemini.embed_content(model=self.model, text=content, config=config)
        return validate_and_normalize(values, self.dimension)

    async def embed_document(self, text: str, title: str | None = None) -> list[float]:
        return await self._embed(text, "document", title)

    async def embed_query(self, text: str) -> list[float]:
        """Cached: repeated searches do not spend quota or add latency."""
        key = " ".join(text.lower().split())
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        vector = await self._embed(text, "query")
        self._cache[key] = vector
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return vector
