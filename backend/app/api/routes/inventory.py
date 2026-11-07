"""Network inventory (synthetic in the demo): sites and nodes knowledge is bound to."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.models import Equipment, KnowledgeEntityLink, Site
from app.services.retrieval.search import normalize_identifier

router = APIRouter(prefix="/inventory", tags=["network inventory"])


class SiteRead(BaseModel):
    site_identifier: str
    name: str | None
    region: str | None
    description: str | None
    knowledge_count: int


class NodeRead(BaseModel):
    equipment_identifier: str
    equipment_type: str | None
    vendor: str | None
    model: str | None
    unit_class: str | None
    installed_year: int | None
    site_identifier: str | None
    knowledge_count: int  # knowledge bound to this node directly
    class_knowledge_count: int  # knowledge bound to its unit class


class InventoryRead(BaseModel):
    sites: list[SiteRead]
    nodes: list[NodeRead]
    note: str = "Synthetic inventory for the demo; a real deployment would sync it from the inventory system."


@router.get("", response_model=InventoryRead, summary="Sites and nodes with linked knowledge counts")
async def inventory(db: DbSession) -> InventoryRead:
    counts: dict[tuple[str, str], int] = {
        (t, k): n for t, k, n in await db.execute(
            select(KnowledgeEntityLink.entity_type, KnowledgeEntityLink.entity_key,
                   func.count(func.distinct(KnowledgeEntityLink.knowledge_item_id)))
            .group_by(KnowledgeEntityLink.entity_type, KnowledgeEntityLink.entity_key))
    }
    sites = [SiteRead(site_identifier=s.site_identifier, name=s.name, region=s.region, description=s.description,
                      knowledge_count=counts.get(("site", normalize_identifier(s.site_identifier)), 0))
             for s in await db.scalars(select(Site).order_by(Site.site_identifier))]
    nodes = [NodeRead(
        equipment_identifier=e.equipment_identifier, equipment_type=e.equipment_type, vendor=e.vendor, model=e.model,
        unit_class=e.unit_class, installed_year=e.installed_year, site_identifier=e.site_identifier,
        knowledge_count=counts.get(("equipment", normalize_identifier(e.equipment_identifier)), 0),
        class_knowledge_count=counts.get(("unit_class", normalize_identifier(e.unit_class)), 0) if e.unit_class else 0,
    ) for e in await db.scalars(select(Equipment).where(Equipment.unit_class.is_not(None))
                                .order_by(Equipment.equipment_identifier))]
    return InventoryRead(sites=sites, nodes=nodes)
