"""Raw communication data: sources, conversation threads and their messages."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, str_enum, tz_datetime
from app.models.enums import SourceType, ThreadProcessingStatus

if TYPE_CHECKING:
    from app.models.knowledge import KnowledgeCandidate, KnowledgeEvidence


class CommunicationSource(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An authorized channel conversations are collected from."""

    __tablename__ = "communication_sources"
    __table_args__ = (UniqueConstraint("source_type", "external_source_id"),)

    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[SourceType] = mapped_column(str_enum(SourceType, "source_type"))
    # ID of the workspace / team / feed in the external system.
    external_source_id: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    threads: Mapped[list["ConversationThread"]] = relationship(back_populates="source")


class ConversationThread(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A discussion made of multiple messages, e.g. a Slack thread or email chain."""

    __tablename__ = "conversation_threads"
    __table_args__ = (
        UniqueConstraint("communication_source_id", "external_thread_id"),
        Index("ix_conversation_threads_last_message_at", "last_message_at"),
    )

    communication_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("communication_sources.id", ondelete="RESTRICT"), index=True
    )
    external_thread_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    last_message_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    processing_status: Mapped[ThreadProcessingStatus] = mapped_column(
        str_enum(ThreadProcessingStatus, "processing_status"),
        default=ThreadProcessingStatus.PENDING,
        server_default=ThreadProcessingStatus.PENDING.value,
        index=True,
    )

    source: Mapped[CommunicationSource] = relationship(back_populates="threads")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread",
        order_by=lambda: [Message.sent_at, Message.external_message_id],
    )
    knowledge_candidates: Mapped[list["KnowledgeCandidate"]] = relationship(
        back_populates="thread"
    )


class Message(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An original message, kept unmodified so it can be shown as evidence.

    Edits and deletions at the source are synchronized through `edited_at` /
    `deleted_at`; rows are never physically removed, so evidence links survive.
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Idempotent ingestion: re-delivering a message updates instead of duplicating.
        UniqueConstraint("thread_id", "external_message_id"),
        # Original ordering within a thread.
        Index("ix_messages_thread_id_sent_at", "thread_id", "sent_at"),
    )

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_threads.id", ondelete="RESTRICT")
    )
    external_message_id: Mapped[str] = mapped_column(String(255))
    author_external_id: Mapped[str] = mapped_column(String(255), index=True)
    author_display_name: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(tz_datetime())
    edited_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    deleted_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    # Permalink back to the original message in Slack/Teams/etc.
    source_url: Mapped[str | None] = mapped_column(String(2048))

    thread: Mapped[ConversationThread] = relationship(back_populates="messages")
    evidence: Mapped[list["KnowledgeEvidence"]] = relationship(back_populates="message")
