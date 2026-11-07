"""Consolidation of related knowledge items (Phase 6B).

Original knowledge items are never modified or merged: groups and relationships are derived
data that point at them. Relationships are stored once per unordered pair (source < target),
so repeated comparisons update the same row.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, tz_datetime

_JSON_LIST = {"default": list, "server_default": text("'[]'::jsonb")}
_JSON_DICT = {"default": dict, "server_default": text("'{}'::jsonb")}

RELATIONSHIP_TYPES = (
    "same_problem",
    "supporting_evidence",
    "same_problem_different_conditions",
    "different_outcome",
    "potentially_conflicting",
    "related_symptoms",
    "unrelated",
)


class KnowledgeGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_groups"

    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    # Structured, validated summary (solutions, conditions, contradictions, missing info).
    summary_data: Mapped[dict[str, Any]] = mapped_column(JSONB, **_JSON_DICT)
    # Hash of the members' content when the summary was generated (skip unchanged groups).
    summary_fingerprint: Mapped[str | None] = mapped_column(String(64))
    summary_model: Mapped[str | None] = mapped_column(String(100))

    members: Mapped[list["KnowledgeGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", passive_deletes=True
    )


class KnowledgeGroupMember(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_group_members"
    # An item belongs to at most one group: ambiguous items stay ungrouped.
    __table_args__ = (UniqueConstraint("knowledge_item_id"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_groups.id", ondelete="CASCADE"), index=True
    )
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_items.id", ondelete="CASCADE"))

    group: Mapped[KnowledgeGroup] = relationship(back_populates="members")


class KnowledgeRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_relationships"
    __table_args__ = (
        UniqueConstraint("source_knowledge_id", "target_knowledge_id"),
        CheckConstraint("source_knowledge_id < target_knowledge_id", "ordered_pair"),
        CheckConstraint(
            "relationship_type IN (" + ", ".join(f"'{t}'" for t in RELATIONSHIP_TYPES) + ")", "relationship_type"
        ),
    )

    source_knowledge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    target_knowledge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(40), index=True)
    outcome_comparison: Mapped[str | None] = mapped_column(String(30))
    explanation: Mapped[str | None] = mapped_column(Text)
    shared_symptoms: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    shared_equipment: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    # [{"field", "source_value", "target_value"}]; None means unknown, never assumed equal.
    conditions: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    unknown_conditions: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    source_evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    target_evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    validation_notes: Mapped[list[Any]] = mapped_column(JSONB, **_JSON_LIST)
    model_name: Mapped[str | None] = mapped_column(String(100))
    # Hash of both items' content at comparison time: unchanged pairs are not re-compared.
    pair_fingerprint: Mapped[str] = mapped_column(String(64))


class KnowledgeConsolidationState(TimestampMixin, Base):
    """Per-item bookkeeping: what was consolidated, and what must be retried."""

    __tablename__ = "knowledge_consolidation_state"

    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20))  # done | retry | skipped
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    consolidated_at: Mapped[datetime | None] = mapped_column(tz_datetime())
