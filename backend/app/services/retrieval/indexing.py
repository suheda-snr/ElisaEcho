"""Keep knowledge_chunks (text + embedding) in sync with knowledge items.

Two steps, each committed separately:
1. `sync_item_chunks` rewrites chunk text (no API calls). Unchanged chunks keep their
   embedding; changed or new chunks get `embedding = NULL`, which marks them for embedding.
   Keyword search works on chunk text right away, even without embeddings.
2. `embed_pending_chunks` embeds chunks whose embedding is NULL. If Gemini fails, the
   chunk simply stays pending for the next attempt (pipeline or backfill command).
Knowledge items and source messages are never deleted here.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiError
from app.models import KnowledgeChunk, KnowledgeItem
from app.services.retrieval.knowledge_text import knowledge_sections, split_into_chunks

logger = logging.getLogger(__name__)


@dataclass
class ChunkSync:
    item_id: uuid.UUID
    chunks: int
    changed: int  # new or rewritten chunks (now pending embedding)
    removed: int


@dataclass
class EmbedResult:
    embedded: int = 0
    pending: int = 0
    error: str | None = None
    retry_after_seconds: float | None = None


@dataclass
class IndexOutcome:
    item_id: uuid.UUID
    status: Literal["unchanged", "indexed", "pending"]
    chunks: int = 0
    embedded: int = 0
    error: str | None = None
    retry_after_seconds: float | None = None
    details: list[str] = field(default_factory=list)


def item_chunk_texts(item: KnowledgeItem) -> list[str]:
    return split_into_chunks(knowledge_sections(
        title=item.title,
        problem_description=item.problem_description,
        symptoms=item.symptoms or [],
        root_cause=item.root_cause,
        resolution=item.resolution,
        resolution_status=item.resolution_status,
        attempted_actions=item.attempted_actions or [],
        applicability_conditions=item.applicability_conditions or [],
        equipment_identifiers=sorted(e.equipment_identifier for e in item.equipment),
        incident_numbers=sorted(i.incident_number for i in item.incidents),
    ))


async def sync_item_chunks(session: AsyncSession, item_id: uuid.UUID, *, commit: bool = True) -> ChunkSync:
    """With commit=False nothing is written (used for dry runs)."""
    item = await session.scalar(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .options(
            selectinload(KnowledgeItem.equipment),
            selectinload(KnowledgeItem.incidents),
            selectinload(KnowledgeItem.chunks),
        )
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise LookupError(item_id)

    texts = item_chunk_texts(item)
    existing = {c.chunk_index: c for c in item.chunks}
    changed = 0
    for index, text in enumerate(texts):
        chunk = existing.pop(index, None)
        if chunk is None:
            session.add(KnowledgeChunk(knowledge_item_id=item.id, chunk_index=index, content=text))
            changed += 1
        elif chunk.content != text:
            chunk.content = text
            chunk.embedding = None  # outdated: re-embed
            changed += 1
    for stale in existing.values():  # item got shorter: drop leftover derived chunks
        await session.delete(stale)
    if commit:
        await session.commit()
    else:
        await session.rollback()
    return ChunkSync(item_id=item_id, chunks=len(texts), changed=changed, removed=len(existing))


async def embed_pending_chunks(
    session: AsyncSession,
    embedder: EmbeddingService,
    *,
    item_id: uuid.UUID | None = None,
    limit: int = 50,
) -> EmbedResult:
    query = (
        select(KnowledgeChunk, KnowledgeItem.title)
        .join(KnowledgeItem, KnowledgeChunk.knowledge_item_id == KnowledgeItem.id)
        .where(KnowledgeChunk.embedding.is_(None))
        .order_by(KnowledgeChunk.created_at, KnowledgeChunk.chunk_index)
        .limit(limit)
    )
    if item_id is not None:
        query = query.where(KnowledgeChunk.knowledge_item_id == item_id)
    rows = (await session.execute(query)).all()

    result = EmbedResult()
    for chunk, title in rows:
        try:
            vector = await embedder.embed_document(chunk.content, title=title)
        except GeminiError as exc:
            logger.warning("Embedding failed for chunk %s: %s", chunk.id, type(exc).__name__)
            result.error = str(exc)
            result.retry_after_seconds = getattr(exc, "retry_after_seconds", None)
            break  # stop on failure: the rest stays pending, nothing is lost
        # Only store if the text was not changed meanwhile (compare-and-set).
        updated = await session.execute(
            update(KnowledgeChunk)
            .where(KnowledgeChunk.id == chunk.id, KnowledgeChunk.content == chunk.content)
            .values(embedding=vector)
        )
        await session.commit()
        result.embedded += updated.rowcount

    pending_query = select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.embedding.is_(None))
    if item_id is not None:
        pending_query = pending_query.where(KnowledgeChunk.knowledge_item_id == item_id)
    result.pending = int(await session.scalar(pending_query) or 0)
    return result


async def index_item(session: AsyncSession, item_id: uuid.UUID, embedder: EmbeddingService) -> IndexOutcome:
    """Sync chunk text, then embed what is pending. Never raises for Gemini problems."""
    sync = await sync_item_chunks(session, item_id)
    if not embedder.configured:
        pending = await embed_pending_count(session, item_id)
        return IndexOutcome(item_id=item_id, status="pending" if pending else "unchanged",
                            chunks=sync.chunks, error="Gemini is not configured.")
    embedded = await embed_pending_chunks(session, embedder, item_id=item_id)
    if embedded.pending:
        return IndexOutcome(item_id=item_id, status="pending", chunks=sync.chunks, embedded=embedded.embedded,
                            error=embedded.error, retry_after_seconds=embedded.retry_after_seconds)
    status = "indexed" if (sync.changed or embedded.embedded) else "unchanged"
    return IndexOutcome(item_id=item_id, status=status, chunks=sync.chunks, embedded=embedded.embedded)


async def embed_pending_count(session: AsyncSession, item_id: uuid.UUID | None = None) -> int:
    query = select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.embedding.is_(None))
    if item_id is not None:
        query = query.where(KnowledgeChunk.knowledge_item_id == item_id)
    return int(await session.scalar(query) or 0)
