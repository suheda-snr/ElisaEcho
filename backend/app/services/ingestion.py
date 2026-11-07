"""Idempotent storage of sources, threads and messages.

Used by the seed script today and by connectors / the simulated feed in Phase 3.
Every function is an upsert keyed on external IDs, so delivering the same data
twice never creates duplicates. Nothing here deletes rows. The caller commits.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommunicationSource, ConversationThread, Message
from app.models.enums import SourceType, ThreadProcessingStatus
from app.schemas.threads import MessageIngest, ThreadIngest


async def upsert_source(
    session: AsyncSession, *, name: str, source_type: SourceType, external_source_id: str
) -> uuid.UUID:
    stmt = (
        insert(CommunicationSource)
        .values(name=name, source_type=source_type, external_source_id=external_source_id)
        .on_conflict_do_update(
            index_elements=["source_type", "external_source_id"],
            set_={"name": name},
        )
        .returning(CommunicationSource.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def upsert_thread(session: AsyncSession, source_id: uuid.UUID, data: ThreadIngest) -> uuid.UUID:
    stmt = (
        insert(ConversationThread)
        .values(
            communication_source_id=source_id,
            external_thread_id=data.external_thread_id,
            title=data.title,
        )
        .on_conflict_do_update(
            index_elements=["communication_source_id", "external_thread_id"],
            # Keep the known title when a later message carries none (e.g. a Slack reply).
            set_={"title": func.coalesce(data.title, ConversationThread.title)},
        )
        .returning(ConversationThread.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def upsert_messages(
    session: AsyncSession, thread_id: uuid.UUID, messages: Iterable[MessageIngest]
) -> int:
    """Insert new messages and synchronize edits/deletions of known ones.

    Returns the number of rows written (inserted or updated).
    """
    rows = [{"thread_id": thread_id, **message.model_dump()} for message in messages]
    if not rows:
        return 0

    stmt = insert(Message).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["thread_id", "external_message_id"],
        set_={
            "content": stmt.excluded.content,
            "author_display_name": stmt.excluded.author_display_name,
            "edited_at": stmt.excluded.edited_at,
            "deleted_at": stmt.excluded.deleted_at,
            "source_url": stmt.excluded.source_url,
        },
    )
    result = await session.execute(stmt)
    await refresh_thread_timestamps(session, thread_id)
    return result.rowcount


async def refresh_thread_timestamps(session: AsyncSession, thread_id: uuid.UUID) -> None:
    """Derive started_at / last_message_at from the thread's messages and queue the
    thread for (re-)analysis. Unchanged content is detected later by fingerprint, so
    re-delivered messages do not trigger new Gemini calls."""
    bounds = (
        select(func.min(Message.sent_at), func.max(Message.sent_at))
        .where(Message.thread_id == thread_id)
    )
    started_at, last_message_at = (await session.execute(bounds)).one()
    await session.execute(
        update(ConversationThread)
        .where(ConversationThread.id == thread_id)
        .values(
            started_at=started_at,
            last_message_at=last_message_at,
            processing_status=ThreadProcessingStatus.PENDING,
        )
    )
