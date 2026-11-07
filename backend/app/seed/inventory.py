"""Synthetic network inventory: sites and nodes with unit class and install year.

Everything here is fictional (identifiers in the style of the Elisa challenge brief). The
inventory lets knowledge be bound to the right entity: a fix learned on TRN-042 that "applies
to these older units" is linked to its unit class, so it is found for TRN-118 as well, but
not presented as known for the newer TRN-305.

`ensure_inventory` only inserts or fills in attributes; it never deletes or overwrites values
that already exist (so a real inventory import would win).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Equipment, Site


@dataclass(frozen=True)
class InventorySite:
    site_identifier: str
    name: str
    region: str
    description: str


@dataclass(frozen=True)
class InventoryNode:
    equipment_identifier: str
    equipment_type: str
    vendor: str
    model: str
    unit_class: str
    installed_year: int
    site_identifier: str


LEGACY_TX = "TX-900 transmission unit (legacy generation)"

SITES: tuple[InventorySite, ...] = (
    InventorySite("SITE-OULU-07", "Oulu Ritaharju transmission hub", "North Ostrobothnia",
                  "Indoor equipment room, badge access."),
    InventorySite("SITE-PELLO-03", "Pello forest radio site 3", "Lapland (Northern Finland)",
                  "Remote site at the end of a private forest road with a locked barrier."),
    InventorySite("SITE-TKU-11", "Turku Kupittaa aggregation site", "Southwest Finland",
                  "Shared telecom building, reception on site."),
    InventorySite("SITE-42", "Site 42 customer edge", "Uusimaa", "Street cabinet."),
    InventorySite("SITE-17", "Site 17 customer edge", "Pirkanmaa", "Street cabinet."),
    InventorySite("SITE-58", "Site 58 customer edge", "Satakunta", "Street cabinet."),
)

NODES: tuple[InventoryNode, ...] = (
    InventoryNode("TRN-042", "transmission node", "Vendor A (synthetic)", "TX-900", LEGACY_TX, 2019, "SITE-OULU-07"),
    InventoryNode("TRN-118", "transmission node", "Vendor A (synthetic)", "TX-900", LEGACY_TX, 2018, "SITE-PELLO-03"),
    InventoryNode("TRN-305", "transmission node", "Vendor A (synthetic)", "TX-2000",
                  "TX-2000 transmission unit (current generation)", 2023, "SITE-TKU-11"),
    InventoryNode("S42-RTR-01", "edge router", "Vendor B (synthetic)", "ER-500", "ER-500 edge router", 2021, "SITE-42"),
    InventoryNode("S17-RTR-02", "edge router", "Vendor B (synthetic)", "ER-500", "ER-500 edge router", 2021, "SITE-17"),
    InventoryNode("S58-RTR-01", "edge router", "Vendor B (synthetic)", "ER-500", "ER-500 edge router", 2022, "SITE-58"),
)


async def ensure_inventory(session: AsyncSession) -> None:
    """Insert missing sites/nodes and fill empty attributes. Caller commits."""
    await session.execute(
        insert(Site).values([s.__dict__ for s in SITES]).on_conflict_do_nothing(index_elements=["site_identifier"])
    )
    await session.execute(
        insert(Equipment).values([{"equipment_identifier": n.equipment_identifier} for n in NODES])
        .on_conflict_do_nothing(index_elements=["equipment_identifier"])
    )
    rows = {e.equipment_identifier: e for e in await session.scalars(
        select(Equipment).where(Equipment.equipment_identifier.in_([n.equipment_identifier for n in NODES])))}
    for node in NODES:
        row = rows[node.equipment_identifier]
        for field in ("equipment_type", "vendor", "model", "unit_class", "installed_year", "site_identifier"):
            if getattr(row, field) is None:
                setattr(row, field, getattr(node, field))
    await session.flush()
