"""Reference entities knowledge is linked to: equipment (network inventory), sites, incidents."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, str_enum, tz_datetime
from app.models.associations import knowledge_item_equipment, knowledge_item_incidents
from app.models.enums import IncidentSeverity, IncidentStatus

if TYPE_CHECKING:
    from app.models.knowledge import KnowledgeItem


class Equipment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "equipment"

    # Network-wide unique identifier, e.g. "ER-114" or "S42-RTR-01".
    equipment_identifier: Mapped[str] = mapped_column(String(100), unique=True)
    equipment_type: Mapped[str | None] = mapped_column(String(100))
    vendor: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    site_identifier: Mapped[str | None] = mapped_column(String(100), index=True)
    # Inventory attributes (synthetic in the demo). Knowledge that says it applies to "these
    # older units" is bound to the unit class, so it is found for sibling nodes too.
    unit_class: Mapped[str | None] = mapped_column(String(100), index=True)
    installed_year: Mapped[int | None] = mapped_column(Integer)

    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        secondary=knowledge_item_equipment, back_populates="equipment"
    )


class Site(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A physical network site (inventory). Access knowledge is bound to sites."""

    __tablename__ = "sites"

    site_identifier: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))
    region: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class Incident(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "incidents"

    incident_number: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IncidentStatus] = mapped_column(
        str_enum(IncidentStatus, "incident_status"),
        default=IncidentStatus.OPEN,
        server_default=IncidentStatus.OPEN.value,
        index=True,
    )
    severity: Mapped[IncidentSeverity | None] = mapped_column(
        str_enum(IncidentSeverity, "incident_severity")
    )
    occurred_at: Mapped[datetime | None] = mapped_column(tz_datetime())
    resolved_at: Mapped[datetime | None] = mapped_column(tz_datetime())

    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        secondary=knowledge_item_incidents, back_populates="incidents"
    )
