"""Bind knowledge (context assertions) to network entities.

Rules (deterministic, server-side):
- equipment named in the conversation  -> equipment / observed_on        (source: conversation)
- its unit class from the inventory    -> unit_class / applies_to         (source: inventory)
  ONLY when the conversation says the knowledge applies to that kind of unit
  (scope = same_equipment_class). Otherwise it stays bound to the single device.
- its site from the inventory          -> site / located_at               (source: inventory)
- sites named in the conversation      -> site / access_to (site access knowledge) or located_at
- operational events mentioned         -> event / triggered_by            (source: conversation)
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Equipment, KnowledgeEntityLink, KnowledgeItem
from app.services.discovery.validation import ValidatedAnalysis
from app.services.retrieval.search import normalize_identifier


def event_key(value: str) -> str:
    return " ".join(value.lower().split())[:200]


@dataclass(frozen=True)
class LinkSpec:
    entity_type: str
    entity_key: str
    label: str
    relation: str
    source: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.entity_type, self.entity_key, self.relation


async def link_specs(session: AsyncSession, validated: ValidatedAnalysis) -> list[LinkSpec]:
    specs: dict[tuple[str, str, str], LinkSpec] = {}

    def add(spec: LinkSpec) -> None:
        if spec.entity_key:
            specs.setdefault(spec.key, spec)

    inventory = {
        normalize_identifier(e.equipment_identifier): e
        for e in await session.scalars(select(Equipment).where(
            Equipment.equipment_identifier.in_(validated.equipment_identifiers)))
    } if validated.equipment_identifiers else {}

    for ident in validated.equipment_identifiers:
        key = normalize_identifier(ident)
        add(LinkSpec("equipment", key, ident, "observed_on", "conversation"))
        node = inventory.get(key)
        if node is None:
            continue
        if node.unit_class and validated.scope == "same_equipment_class":
            add(LinkSpec("unit_class", normalize_identifier(node.unit_class), node.unit_class, "applies_to",
                         "inventory"))
        if node.site_identifier:
            add(LinkSpec("site", normalize_identifier(node.site_identifier), node.site_identifier, "located_at",
                         "inventory"))
    relation = "access_to" if validated.knowledge_type == "site_access" else "located_at"
    for site in validated.site_identifiers:
        add(LinkSpec("site", normalize_identifier(site), site, relation, "conversation"))
    for event in validated.trigger_events:
        add(LinkSpec("event", event_key(event), event, "triggered_by", "conversation"))
    return list(specs.values())


def sync_links(item: KnowledgeItem, specs: list[LinkSpec]) -> None:
    """Update in place: keep matching rows, add new ones, drop the rest (no unique clashes)."""
    wanted = {s.key: s for s in specs}
    kept = []
    for link in item.entity_links:
        spec = wanted.pop((link.entity_type, link.entity_key, link.relation), None)
        if spec is not None:
            link.label, link.source = spec.label[:300], spec.source
            kept.append(link)
    for spec in wanted.values():
        kept.append(KnowledgeEntityLink(entity_type=spec.entity_type, entity_key=spec.entity_key,
                                        label=spec.label[:300], relation=spec.relation, source=spec.source))
    item.entity_links = kept
