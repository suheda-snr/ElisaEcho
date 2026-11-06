"""Many-to-many association tables."""

from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base

knowledge_item_equipment = Table(
    "knowledge_item_equipment",
    Base.metadata,
    Column(
        "knowledge_item_id",
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "equipment_id",
        ForeignKey("equipment.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

knowledge_item_incidents = Table(
    "knowledge_item_incidents",
    Base.metadata,
    Column(
        "knowledge_item_id",
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "incident_id",
        ForeignKey("incidents.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)
