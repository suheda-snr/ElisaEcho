"""State shared between the slack-worker process and the API.

The worker owns the Socket Mode connection; the API only reads this state, so the
Integrations page can show the real connection status without holding a connection itself.
No tokens or secrets are stored here.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, tz_datetime


class IntegrationState(TimestampMixin, Base):
    __tablename__ = "integration_state"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)  # e.g. "slack"
    # disabled | not_configured | connecting | connected | disconnected | error
    status: Mapped[str] = mapped_column(String(30))
    connection_mode: Mapped[str | None] = mapped_column(String(40))
    workspace_id: Mapped[str | None] = mapped_column(String(64))
    workspace_name: Mapped[str | None] = mapped_column(String(200))
    bot_user_id: Mapped[str | None] = mapped_column(String(64))
    # True only after auth.test succeeded AND the Socket Mode connection is open.
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    credentials_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_event_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    last_ingested_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    heartbeat_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    last_error: Mapped[str | None] = mapped_column(Text)


class IntegrationEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Operational log of the connector (no message content)."""

    __tablename__ = "integration_events"
    __table_args__ = (Index("ix_integration_events_integration_created_at", "integration", "created_at"),)

    integration: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(10))  # info | success | warning | error
    message: Mapped[str] = mapped_column(Text)
    channel_id: Mapped[str | None] = mapped_column(String(64))
    thread_id: Mapped[uuid.UUID | None] = mapped_column()


class EmailConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A real mailbox read over IMAP (read-only; messages are never modified or marked read).

    Only one folder/label is read, and only emails from the last `since_days` days, at most
    `max_per_poll` per check. The password is stored encrypted (Fernet, key kept on the server
    in backend/.local/ or EMAIL_CREDENTIALS_KEY) and is never returned by the API or logged.
    """

    __tablename__ = "email_connections"
    __table_args__ = (UniqueConstraint("host", "username", "folder", name="uq_email_connections_account_folder"),)

    host: Mapped[str] = mapped_column(String(200))
    port: Mapped[int] = mapped_column(Integer, default=993)
    username: Mapped[str] = mapped_column(String(200))
    password_encrypted: Mapped[str] = mapped_column(Text)
    folder: Mapped[str] = mapped_column(String(200))
    since_days: Mapped[int] = mapped_column(Integer, default=3)
    max_per_poll: Mapped[int] = mapped_column(Integer, default=10)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="connecting")  # connected | error | connecting
    last_error: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    # IMAP bookkeeping: emails up to last_uid were read; reset if the folder's UIDVALIDITY changes.
    uid_validity: Mapped[int | None] = mapped_column(BigInteger)
    last_uid: Mapped[int | None] = mapped_column(BigInteger)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    folder_message_count: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("communication_sources.id", ondelete="SET NULL", name="fk_email_connections_source")
    )
