"""Message uniqueness and idempotent ingestion."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationThread, Message
from app.models.enums import SourceType
from app.schemas.threads import MessageIngest, ThreadIngest
from app.services.ingestion import upsert_messages, upsert_source, upsert_thread

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


async def _thread_id(session: AsyncSession, external_thread_id: str = "thr-1"):
    source_id = await upsert_source(
        session, name="Ingest test", source_type=SourceType.SIMULATED, external_source_id="ingest-test"
    )
    return await upsert_thread(session, source_id, ThreadIngest(external_thread_id=external_thread_id))


def _message(n: int, content: str = "hello", **extra) -> MessageIngest:
    return MessageIngest(
        external_message_id=f"m{n}",
        author_external_id="u1",
        content=content,
        sent_at=T0 + timedelta(minutes=n),
        **extra,
    )


async def _count(session: AsyncSession, thread_id) -> int:
    return await session.scalar(select(func.count()).where(Message.thread_id == thread_id))


async def test_duplicate_message_in_same_thread_is_rejected(db_session: AsyncSession) -> None:
    thread_id = await _thread_id(db_session)
    db_session.add(Message(thread_id=thread_id, external_message_id="dup", author_external_id="u", content="a", sent_at=T0))
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                Message(thread_id=thread_id, external_message_id="dup", author_external_id="u", content="b", sent_at=T0)
            )
            await db_session.flush()


async def test_same_external_message_id_allowed_in_different_threads(db_session: AsyncSession) -> None:
    first = await _thread_id(db_session, "thr-1")
    second = await _thread_id(db_session, "thr-2")
    await upsert_messages(db_session, first, [_message(1)])
    await upsert_messages(db_session, second, [_message(1)])
    assert await _count(db_session, first) == 1
    assert await _count(db_session, second) == 1


async def test_reingesting_the_same_messages_creates_no_duplicates(db_session: AsyncSession) -> None:
    thread_id = await _thread_id(db_session)
    batch = [_message(1), _message(2), _message(3)]
    await upsert_messages(db_session, thread_id, batch)
    await upsert_messages(db_session, thread_id, batch)
    # Re-upserting source and thread is idempotent too.
    assert await _thread_id(db_session) == thread_id
    assert await _count(db_session, thread_id) == 3


async def test_edits_and_deletions_are_synchronized(db_session: AsyncSession) -> None:
    thread_id = await _thread_id(db_session)
    await upsert_messages(db_session, thread_id, [_message(1, "Restart the router")])
    edited_at = T0 + timedelta(hours=1)
    await upsert_messages(
        db_session, thread_id, [_message(1, "Restart the service, not the router", edited_at=edited_at)]
    )
    message = await db_session.scalar(select(Message).where(Message.thread_id == thread_id))
    await db_session.refresh(message)
    assert message.content == "Restart the service, not the router"
    assert message.edited_at == edited_at

    deleted_at = T0 + timedelta(hours=2)
    await upsert_messages(
        db_session, thread_id, [_message(1, "Restart the service, not the router", deleted_at=deleted_at)]
    )
    await db_session.refresh(message)
    assert message.deleted_at == deleted_at  # soft-synchronized, row kept for evidence
    assert await _count(db_session, thread_id) == 1


async def test_thread_time_range_follows_messages(db_session: AsyncSession) -> None:
    thread_id = await _thread_id(db_session)
    await upsert_messages(db_session, thread_id, [_message(5), _message(2)])
    thread = await db_session.get(ConversationThread, thread_id)
    await db_session.refresh(thread)
    assert thread.started_at == T0 + timedelta(minutes=2)
    assert thread.last_message_at == T0 + timedelta(minutes=5)
