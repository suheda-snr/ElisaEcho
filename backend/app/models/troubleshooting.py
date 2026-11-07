"""Generated troubleshooting guides (decision trees) and engineers' sessions through them.

Guides reference existing knowledge and messages; nothing is copied or duplicated.
Session steps are append-only: revising an answer marks later steps as superseded
instead of deleting them, so the full history is preserved.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, str_enum, tz_datetime
from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    GuideNodeType,
    GuideStatus,
    SessionStatus,
    SessionStepType,
    SupportLevel,
)

_JSON_LIST = {"default": list, "server_default": text("'[]'::jsonb")}


class TroubleshootingGuide(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "troubleshooting_guides"

    title: Mapped[str] = mapped_column(String(500))
    problem_description: Mapped[str] = mapped_column(Text)
    equipment_identifier: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[GuideStatus] = mapped_column(str_enum(GuideStatus, "guide_status"), index=True)
    # Why the guide could not be generated (insufficient evidence), if applicable.
    status_reason: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(100))
    source_knowledge_ids: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    conflicts: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    uncertainties: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    # Validation notes (e.g. ignored evidence references) for transparency.
    validation_notes: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)

    nodes: Mapped[list["GuideNode"]] = relationship(
        back_populates="guide", cascade="all, delete-orphan", passive_deletes=True,
        order_by=lambda: GuideNode.position,
    )
    edges: Mapped[list["GuideEdge"]] = relationship(
        back_populates="guide", cascade="all, delete-orphan", passive_deletes=True,
    )
    sessions: Mapped[list["TroubleshootingSession"]] = relationship(
        back_populates="guide", passive_deletes=True
    )


class GuideNode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "guide_nodes"
    __table_args__ = (UniqueConstraint("guide_id", "node_key"),)

    guide_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("troubleshooting_guides.id", ondelete="CASCADE"), index=True
    )
    node_key: Mapped[str] = mapped_column(String(40))  # stable id within the guide, e.g. "n3"
    position: Mapped[int] = mapped_column(Integer)
    node_type: Mapped[GuideNodeType] = mapped_column(str_enum(GuideNodeType, "guide_node_type"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str | None] = mapped_column(Text)
    expected_answers: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    applicability_conditions: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    knowledge_item_ids: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    # Derived from the source knowledge, never taken from the model.
    approval_status: Mapped[ApprovalStatus | None] = mapped_column(str_enum(ApprovalStatus, "node_approval_status"))
    support_level: Mapped[SupportLevel] = mapped_column(str_enum(SupportLevel, "support_level"))
    requires_manual_verification: Mapped[bool] = mapped_column(Boolean)
    conflict_note: Mapped[str | None] = mapped_column(Text)

    guide: Mapped[TroubleshootingGuide] = relationship(back_populates="nodes")
    evidence: Mapped[list["NodeEvidence"]] = relationship(
        back_populates="node", cascade="all, delete-orphan", passive_deletes=True
    )


class GuideEdge(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "guide_edges"
    __table_args__ = (UniqueConstraint("source_node_id", "answer_label"),)

    guide_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("troubleshooting_guides.id", ondelete="CASCADE"), index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guide_nodes.id", ondelete="CASCADE"))
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guide_nodes.id", ondelete="CASCADE"), index=True
    )
    answer_label: Mapped[str] = mapped_column(String(100))
    condition: Mapped[str | None] = mapped_column(Text)

    guide: Mapped[TroubleshootingGuide] = relationship(back_populates="edges")


class NodeEvidence(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Links a guide step to an original message (validated against retrieval results)."""

    __tablename__ = "node_evidence"
    __table_args__ = (UniqueConstraint("node_id", "message_id"),)

    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guide_nodes.id", ondelete="CASCADE"), index=True)
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="RESTRICT"), index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="RESTRICT"), index=True)
    evidence_type: Mapped[EvidenceType] = mapped_column(str_enum(EvidenceType, "node_evidence_type"))

    node: Mapped[GuideNode] = relationship(back_populates="evidence")


class TroubleshootingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "troubleshooting_sessions"

    guide_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("troubleshooting_guides.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        str_enum(SessionStatus, "session_status"),
        default=SessionStatus.IN_PROGRESS,
        server_default=SessionStatus.IN_PROGRESS.value,
        index=True,
    )
    current_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("guide_nodes.id", ondelete="SET NULL")
    )
    # Reported by the engineer at completion. Never promoted to knowledge automatically.
    outcome_summary: Mapped[str | None] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(tz_datetime())

    guide: Mapped[TroubleshootingGuide] = relationship(back_populates="sessions")
    steps: Mapped[list["SessionStep"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True,
        order_by=lambda: SessionStep.sequence,
    )


class SessionStep(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "session_steps"
    __table_args__ = (UniqueConstraint("session_id", "sequence"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("troubleshooting_sessions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[SessionStepType] = mapped_column(str_enum(SessionStepType, "session_step_type"))
    node_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("guide_nodes.id", ondelete="CASCADE"))
    answer_label: Mapped[str | None] = mapped_column(String(100))
    target_node_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("guide_nodes.id", ondelete="CASCADE"))
    observation: Mapped[str | None] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text)
    # True once the engineer went back past this answer; kept for history, not on the active path.
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    session: Mapped[TroubleshootingSession] = relationship(back_populates="steps")
