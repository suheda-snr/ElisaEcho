"""Store Slack messages through the existing ingestion pipeline and trigger analysis.

Grouping: one communication source per Slack channel (`team:channel`), one conversation
thread per Slack thread (`channel:thread_ts`), one message per Slack `ts`. Different channels
or workspaces can therefore never share a thread, and re-delivered events upsert instead of
duplicating. Analysis is scheduled only after the transaction committed.
"""

import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommunicationSource, ConversationThread, Message
from app.models.enums import SourceType
from app.schemas.threads import MessageIngest, ThreadIngest
from app.services.ingestion import refresh_thread_timestamps, upsert_messages, upsert_thread
from app.services.integrations import SLACK, log_event, update_state
from app.slack.events import (
    Ignored,
    SlackMessage,
    normalize_text,
    parse_event,
    source_external_id,
    thread_external_id,
    ts_to_datetime,
)

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class SlackDirectory(Protocol):
    """Read-only Slack lookups (names, links). Implementations must not invent data."""

    async def user_name(self, user_id: str) -> str | None: ...
    async def permalink(self, channel_id: str, ts: str) -> str | None: ...
    async def thread_title(self, channel_id: str, thread_ts: str) -> str | None: ...
    def cached_user_name(self, user_id: str) -> str | None: ...


@dataclass(frozen=True)
class IngestResult:
    status: Literal["stored", "updated", "deleted", "ignored", "not_monitored", "unknown_message"]
    reason: str | None = None
    thread_id: uuid.UUID | None = None


def _title(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return first_line[:120] + ("…" if len(first_line) > 120 else "")


async def monitored_source(session: AsyncSession, team_id: str, channel_id: str) -> CommunicationSource | None:
    """Allowlist check: only explicitly enabled channels are ingested."""
    return await session.scalar(
        select(CommunicationSource).where(
            CommunicationSource.source_type == SourceType.SLACK,
            CommunicationSource.external_source_id == source_external_id(team_id, channel_id),
            CommunicationSource.enabled.is_(True),
        )
    )


class SlackIngestor:
    def __init__(
        self,
        session_factory: SessionFactory,
        directory: SlackDirectory,
        schedule_analysis: Callable[[uuid.UUID, str | None], None],
        bot_user_id: str | None,
    ) -> None:
        self.session_factory = session_factory
        self.directory = directory
        self.schedule_analysis = schedule_analysis
        self.bot_user_id = bot_user_id

    async def handle_payload(self, payload: dict) -> IngestResult:
        parsed = parse_event(payload, self.bot_user_id)
        if isinstance(parsed, Ignored):
            return IngestResult("ignored", parsed.reason)
        return await self.handle_message(parsed)

    async def handle_message(self, msg: SlackMessage) -> IngestResult:
        # Slack lookups happen before the transaction so it stays short.
        author = await self.directory.user_name(msg.user_id) if msg.user_id else None
        text = normalize_text(msg.text, self.directory.cached_user_name) if msg.text else ""
        permalink = await self.directory.permalink(msg.channel_id, msg.ts) if msg.kind != "deleted" else None
        title = None
        if msg.kind == "new":
            title = _title(text) if not msg.is_reply else await self.directory.thread_title(msg.channel_id, msg.thread_ts)

        async with self.session_factory() as session:
            source = await monitored_source(session, msg.team_id, msg.channel_id)
            now = datetime.now(UTC)
            await update_state(session, SLACK, last_event_at=now)
            if source is None:
                await session.commit()
                return IngestResult("not_monitored", f"channel {msg.channel_id} is not enabled")

            if msg.kind == "deleted":
                result = await self._mark_deleted(session, source.id, msg)
            else:
                thread_id = await upsert_thread(
                    session, source.id,
                    ThreadIngest(external_thread_id=thread_external_id(msg.channel_id, msg.thread_ts), title=title),
                )
                await upsert_messages(session, thread_id, [MessageIngest(
                    external_message_id=msg.ts,
                    author_external_id=msg.user_id or "unknown",
                    author_display_name=author,
                    content=text,
                    sent_at=ts_to_datetime(msg.ts),
                    edited_at=ts_to_datetime(msg.edited_ts) if msg.edited_ts else None,
                    source_url=permalink,
                )])
                result = IngestResult("updated" if msg.kind == "edited" else "stored", thread_id=thread_id)

            if result.thread_id is not None:
                verb = {"stored": "New message", "updated": "Edited message", "deleted": "Deleted message"}[result.status]
                await log_event(session, SLACK, "message_" + result.status,
                                f"{verb} from {author or msg.user_id or 'unknown user'} in {source.name}",
                                level="info", channel_id=msg.channel_id, thread_id=result.thread_id)
                await update_state(session, SLACK, last_event_at=now, last_ingested_at=now)
            await session.commit()  # persisted before anything is reported or analyzed

        if result.thread_id is not None:
            self.schedule_analysis(result.thread_id, title)
        return result

    async def _mark_deleted(self, session: AsyncSession, source_id: uuid.UUID, msg: SlackMessage) -> IngestResult:
        thread_id = await session.scalar(
            select(ConversationThread.id).where(
                ConversationThread.communication_source_id == source_id,
                ConversationThread.external_thread_id == thread_external_id(msg.channel_id, msg.thread_ts),
            )
        )
        if thread_id is None:
            return IngestResult("unknown_message", "deleted message was never ingested")
        updated = await session.execute(
            update(Message)
            .where(Message.thread_id == thread_id, Message.external_message_id == msg.ts)
            .values(deleted_at=datetime.now(UTC))
        )
        if updated.rowcount == 0:
            return IngestResult("unknown_message", "deleted message was never ingested")
        # Re-queue the thread: re-analysis drops evidence that relied on the deleted message.
        await refresh_thread_timestamps(session, thread_id)
        return IngestResult("deleted", thread_id=thread_id)
