"""Seeding against the isolated test database."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import CommunicationSource, ConversationThread, KnowledgeCandidate, KnowledgeItem, Message
from app.models.enums import ThreadProcessingStatus
from app.seed.demo_data import DEMO_SOURCE_EXTERNAL_ID, DEMO_THREADS
from app.seed.seed import SeedNotAllowedError, seed_demo_data


async def _demo_counts(session: AsyncSession) -> tuple[int, int, int]:
    source_filter = CommunicationSource.external_source_id == DEMO_SOURCE_EXTERNAL_ID
    sources = await session.scalar(select(func.count()).select_from(CommunicationSource).where(source_filter))
    threads = await session.scalar(
        select(func.count()).select_from(ConversationThread).join(ConversationThread.source).where(source_filter)
    )
    messages = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Message.thread)
        .join(ConversationThread.source)
        .where(source_filter)
    )
    return sources, threads, messages


async def test_seed_is_idempotent(db_session: AsyncSession, test_settings: Settings) -> None:
    chat = [t for t in DEMO_THREADS if t.source == "chat"]
    expected_messages = sum(len(t.messages) for t in chat)

    first = await seed_demo_data(db_session, test_settings)
    after_first = await _demo_counts(db_session)
    second = await seed_demo_data(db_session, test_settings)
    after_second = await _demo_counts(db_session)

    assert first == second
    assert after_first == after_second == (1, len(chat), expected_messages)
    # Plus the Teams threads and the demo emails (3 emails in 2 threads), never duplicated.
    assert first.threads == len(DEMO_THREADS) + 2
    assert first.messages == sum(len(t.messages) for t in DEMO_THREADS) + 3


async def test_seed_stores_only_conversations_for_phase_3(
    db_session: AsyncSession, test_settings: Settings
) -> None:
    knowledge_before = await db_session.scalar(select(func.count()).select_from(KnowledgeItem))
    candidates_before = await db_session.scalar(select(func.count()).select_from(KnowledgeCandidate))

    await seed_demo_data(db_session, test_settings)

    assert await db_session.scalar(select(func.count()).select_from(KnowledgeItem)) == knowledge_before
    assert await db_session.scalar(select(func.count()).select_from(KnowledgeCandidate)) == candidates_before
    statuses = set(
        await db_session.scalars(
            select(ConversationThread.processing_status)
            .join(ConversationThread.source)
            .where(CommunicationSource.external_source_id == DEMO_SOURCE_EXTERNAL_ID)
        )
    )
    assert statuses == {ThreadProcessingStatus.PENDING}


async def test_seed_preserves_source_references(db_session: AsyncSession, test_settings: Settings) -> None:
    await seed_demo_data(db_session, test_settings)
    urls = list(
        await db_session.scalars(
            select(Message.source_url)
            .join(Message.thread)
            .join(ConversationThread.source)
            .where(CommunicationSource.external_source_id == DEMO_SOURCE_EXTERNAL_ID)
        )
    )
    assert urls and all(url and ".invalid/" in url for url in urls)


async def test_seed_refuses_in_production(db_session: AsyncSession) -> None:
    before = await _demo_counts(db_session)
    with pytest.raises(SeedNotAllowedError):
        await seed_demo_data(db_session, Settings(_env_file=None, environment="production"))
    assert await _demo_counts(db_session) == before
