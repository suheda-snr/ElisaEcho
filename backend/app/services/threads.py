import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ConversationThread, Message
from app.models.enums import ThreadProcessingStatus

_message_count = (
    select(func.count(Message.id))
    .where(Message.thread_id == ConversationThread.id)
    .correlate(ConversationThread)
    .scalar_subquery()
    .label("message_count")
)


def _with_count(rows) -> list[ConversationThread]:
    threads = []
    for thread, count in rows:
        # Plain attribute used by the response schema; not a mapped column.
        thread.message_count = count
        threads.append(thread)
    return threads


async def list_threads(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    source_id: uuid.UUID | None = None,
    processing_status: ThreadProcessingStatus | None = None,
) -> tuple[list[ConversationThread], int]:
    query: Select = select(ConversationThread)
    if source_id is not None:
        query = query.where(ConversationThread.communication_source_id == source_id)
    if processing_status is not None:
        query = query.where(ConversationThread.processing_status == processing_status)

    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await session.execute(
        query.add_columns(_message_count)
        .order_by(
            ConversationThread.last_message_at.desc().nulls_last(),
            ConversationThread.created_at.desc(),
            ConversationThread.id,
        )
        .limit(limit)
        .offset(offset)
    )
    return _with_count(rows.all()), total


async def get_thread(session: AsyncSession, thread_id: uuid.UUID) -> ConversationThread | None:
    rows = await session.execute(
        select(ConversationThread, _message_count)
        .options(selectinload(ConversationThread.source))
        .where(ConversationThread.id == thread_id)
    )
    threads = _with_count(rows.all())
    return threads[0] if threads else None


async def thread_exists(session: AsyncSession, thread_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(select(select(ConversationThread.id).where(ConversationThread.id == thread_id).exists()))
    )


async def list_messages(
    session: AsyncSession, thread_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Message], int]:
    """Messages in original order (sent time, then the source's own message ID)."""
    total = (
        await session.scalar(select(func.count()).where(Message.thread_id == thread_id)) or 0
    )
    result = await session.scalars(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.sent_at, Message.external_message_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result), total
