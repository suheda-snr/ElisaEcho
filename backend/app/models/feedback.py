"""Engineers' reports on whether a troubleshooting recommendation worked (Phase 6C).

Feedback is a second evidence origin next to conversation messages. It never modifies the
original knowledge (its resolution or approval status) or its Slack evidence. One row per
(session, recommendation, knowledge item): repeated submissions update that row and keep
the previous versions in `revisions`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, tz_datetime

FEEDBACK_OUTCOMES = ("resolved", "not_resolved", "partially_resolved", "unknown", "not_attempted")
VERIFICATION_STATUSES = ("self_reported", "independently_verified")


class TroubleshootingFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "troubleshooting_feedback"
    __table_args__ = (
        UniqueConstraint("troubleshooting_session_id", "guide_node_id", "knowledge_item_id",
                         name="uq_feedback_session_node_knowledge"),
        CheckConstraint("outcome IN (" + ", ".join(f"'{o}'" for o in FEEDBACK_OUTCOMES) + ")", "feedback_outcome"),
        CheckConstraint("verification_status IN (" + ", ".join(f"'{v}'" for v in VERIFICATION_STATUSES) + ")",
                        "feedback_verification_status"),
        # Not attempted <=> no outcome; an attempt always has a real outcome.
        CheckConstraint("attempted = (outcome <> 'not_attempted')", "feedback_attempt_consistent"),
    )

    troubleshooting_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("troubleshooting_sessions.id", ondelete="CASCADE", name="fk_feedback_session"), index=True
    )
    guide_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guide_nodes.id", ondelete="CASCADE", name="fk_feedback_guide_node"))
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE", name="fk_feedback_knowledge_item"), index=True
    )
    attempted: Mapped[bool] = mapped_column(Boolean)
    outcome: Mapped[str] = mapped_column(String(30), index=True)
    equipment_identifier: Mapped[str | None] = mapped_column(String(100))
    firmware_version: Mapped[str | None] = mapped_column(String(100))
    environment_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    engineer_notes: Mapped[str | None] = mapped_column(Text)
    # Only an authorized verification workflow may set independently_verified (none exists yet).
    verification_status: Mapped[str] = mapped_column(
        String(30), default="self_reported", server_default=text("'self_reported'")
    )
    submitted_at: Mapped[datetime] = mapped_column(tz_datetime(), server_default=text("now()"))
    # No user accounts exist: the submitter receives a one-time secret; only its hash is stored.
    edit_token_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    # Previous versions (audit history), oldest first.
    revisions: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
