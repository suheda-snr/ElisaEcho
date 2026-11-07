"""Knowledge discovered in conversations, its evidence and its search chunks."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, str_enum, tz_datetime
from app.models.associations import knowledge_item_equipment, knowledge_item_incidents
from app.models.communication import ConversationThread, Message
from app.models.enums import ApprovalStatus, DetectionStatus, EvidenceType, KnowledgeType, ResolutionStatus
from app.models.reference import Equipment, Incident

# Every stored and query embedding must have exactly this many dimensions.
# Phase 4 must request this size explicitly from the embedding model
# (e.g. Gemini `output_dimensionality=768`). Changing it requires a migration.
EMBEDDING_DIMENSION = 768


class KnowledgeCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Potential knowledge the AI detected in a thread, possibly before any fix is confirmed."""

    __tablename__ = "knowledge_candidates"
    __table_args__ = (
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", "confidence_range"),
    )

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_threads.id", ondelete="RESTRICT"), index=True
    )
    # Free-form label from the detector, e.g. "troubleshooting_resolution", "workaround".
    candidate_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    detection_status: Mapped[DetectionStatus] = mapped_column(
        str_enum(DetectionStatus, "detection_status"),
        default=DetectionStatus.DETECTED,
        server_default=DetectionStatus.DETECTED.value,
        index=True,
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    # Raw structured output of the model, kept for auditing and re-processing.
    extracted_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    model_name: Mapped[str | None] = mapped_column(String(100))

    thread: Mapped[ConversationThread] = relationship(back_populates="knowledge_candidates")
    knowledge_item: Mapped["KnowledgeItem | None"] = relationship(back_populates="candidate")


class KnowledgeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured operational knowledge.

    `resolution_status` says what the conversation showed; `approval_status` says
    whether an expert has approved it. Confirmation in chat never implies approval.
    """

    __tablename__ = "knowledge_items"

    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_candidates.id", ondelete="SET NULL"), unique=True
    )
    title: Mapped[str] = mapped_column(String(500))
    problem_description: Mapped[str] = mapped_column(Text)
    symptoms: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    root_cause: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    attempted_actions: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    applicability_conditions: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    resolution_status: Mapped[ResolutionStatus] = mapped_column(
        str_enum(ResolutionStatus, "resolution_status"),
        default=ResolutionStatus.UNKNOWN,
        server_default=ResolutionStatus.UNKNOWN.value,
        index=True,
    )
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        str_enum(ApprovalStatus, "approval_status"),
        default=ApprovalStatus.UNREVIEWED,
        server_default=ApprovalStatus.UNREVIEWED.value,
        index=True,
    )
    knowledge_type: Mapped[KnowledgeType] = mapped_column(
        str_enum(KnowledgeType, "knowledge_type"),
        default=KnowledgeType.TROUBLESHOOTING,
        server_default=KnowledgeType.TROUBLESHOOTING.value,
        index=True,
    )
    # Time validity of the context assertion. valid_from: first evidence message;
    # valid_to NULL means "still believed true". Set when newer knowledge replaces it.
    valid_from: Mapped[datetime | None] = mapped_column(tz_datetime(), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(tz_datetime(), index=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="SET NULL", name="fk_knowledge_items_superseded_by")
    )
    validity_note: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[KnowledgeCandidate | None] = relationship(back_populates="knowledge_item")
    evidence: Mapped[list["KnowledgeEvidence"]] = relationship(
        back_populates="knowledge_item", cascade="all, delete-orphan", passive_deletes=True
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="knowledge_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: KnowledgeChunk.chunk_index,
    )
    equipment: Mapped[list[Equipment]] = relationship(
        secondary=knowledge_item_equipment, back_populates="knowledge_items"
    )
    incidents: Mapped[list[Incident]] = relationship(
        secondary=knowledge_item_incidents, back_populates="knowledge_items"
    )
    entity_links: Mapped[list["KnowledgeEntityLink"]] = relationship(
        back_populates="knowledge_item", cascade="all, delete-orphan", passive_deletes=True
    )


class KnowledgeEvidence(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Links a knowledge item to an exact source message and says what it proves."""

    __tablename__ = "knowledge_evidence"
    __table_args__ = (UniqueConstraint("knowledge_item_id", "message_id", "evidence_type"),)

    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT: a message cannot be removed while it is cited as evidence.
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), index=True
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(str_enum(EvidenceType, "evidence_type"))
    explanation: Mapped[str | None] = mapped_column(Text)

    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="evidence")
    message: Mapped[Message] = relationship(back_populates="evidence")


class KnowledgeChunk(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A searchable piece of a knowledge item with its embedding (filled in Phase 4)."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("knowledge_item_id", "chunk_index"),
        # Approximate nearest-neighbour index for cosine-distance search.
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Full-text search; must match the expression used in app/services/retrieval/search.py.
        Index(
            "ix_knowledge_chunks_content_fts",
            text("to_tsvector('english'::regconfig, content)"),
            postgresql_using="gin",
        ),
    )

    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer)
    # Nullable: chunks may exist before their embedding is generated.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))

    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="chunks")


ENTITY_TYPES = ("equipment", "unit_class", "site", "event")
ENTITY_RELATIONS = ("observed_on", "applies_to", "located_at", "access_to", "triggered_by")


class KnowledgeEntityLink(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Binds a knowledge item (a context assertion) to a network entity.

    - equipment / observed_on: the node the conversation was about (e.g. TRN-042)
    - unit_class / applies_to: the class of units it applies to, from the inventory, only when
      the conversation itself says it applies to "these/older units" (scope = same class)
    - site / located_at or access_to: the site of the node, or the site that access info is for
    - event / triggered_by: the operational event the knowledge is about (e.g. SFP replacement)
    `source` says whether the link was stated in the conversation or derived from the inventory.
    """

    __tablename__ = "knowledge_entity_links"
    __table_args__ = (
        UniqueConstraint("knowledge_item_id", "entity_type", "entity_key", "relation",
                         name="uq_entity_links_item_entity_relation"),
        CheckConstraint("entity_type IN (" + ", ".join(f"'{t}'" for t in ENTITY_TYPES) + ")", "entity_type"),
        CheckConstraint("relation IN (" + ", ".join(f"'{r}'" for r in ENTITY_RELATIONS) + ")", "relation"),
        CheckConstraint("source IN ('conversation', 'inventory')", "link_source"),
    )

    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(20))
    # Normalized key used for matching (lower case, no spaces/dashes), e.g. "trn042".
    entity_key: Mapped[str] = mapped_column(String(200), index=True)
    label: Mapped[str] = mapped_column(String(300))
    relation: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))

    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="entity_links")
