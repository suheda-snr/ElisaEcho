"""Find knowledge items worth comparing with a given item (bounded, never all-pairs).

Signals: cosine similarity of the item's stored embedding (Phase 4 chunks) and shared
structured identifiers (equipment). Only knowledge from authorized (enabled) sources is
considered. Similarity only nominates candidates; Gemini and validation decide relationships.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeChunk, KnowledgeEntityLink, KnowledgeItem, knowledge_item_equipment
from app.models.enums import ApprovalStatus
from app.services.retrieval.search import SearchFilters, allowed_items


@dataclass(frozen=True)
class Candidate:
    knowledge_id: uuid.UUID
    similarity: float | None  # None when found only via shared identifiers
    shared_identifier: bool


def eligible_items() -> Select:
    """Items that take part in consolidation: from enabled sources, not rejected by an expert."""
    return allowed_items(SearchFilters(include_outdated=True)).where(
        KnowledgeItem.approval_status != ApprovalStatus.REJECTED)


async def find_candidates(
    session: AsyncSession, item_id: uuid.UUID, *, limit: int, min_similarity: float
) -> list[Candidate]:
    allowed = eligible_items()
    found: dict[uuid.UUID, Candidate] = {}

    vectors = list(await session.scalars(
        select(KnowledgeChunk.embedding).where(
            KnowledgeChunk.knowledge_item_id == item_id, KnowledgeChunk.embedding.is_not(None))
    ))
    for vector in vectors:
        distance = KnowledgeChunk.embedding.cosine_distance(vector)
        rows = await session.execute(
            select(KnowledgeChunk.knowledge_item_id, distance)
            .where(KnowledgeChunk.embedding.is_not(None), KnowledgeChunk.knowledge_item_id != item_id,
                   KnowledgeChunk.knowledge_item_id.in_(allowed))
            .order_by(distance)
            .limit(limit * 3)
        )
        for other_id, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity >= min_similarity:
                previous = found.get(other_id)
                if previous is None or (previous.similarity or 0) < similarity:
                    found[other_id] = Candidate(other_id, similarity, False)

    my_equipment = select(knowledge_item_equipment.c.equipment_id).where(
        knowledge_item_equipment.c.knowledge_item_id == item_id)
    shared = await session.scalars(
        select(knowledge_item_equipment.c.knowledge_item_id).distinct().where(
            knowledge_item_equipment.c.equipment_id.in_(my_equipment),
            knowledge_item_equipment.c.knowledge_item_id != item_id,
            knowledge_item_equipment.c.knowledge_item_id.in_(allowed))
    )
    # Also the same node or site through entity links (e.g. two access notes for one site).
    my_entities = select(KnowledgeEntityLink.entity_key).where(
        KnowledgeEntityLink.knowledge_item_id == item_id, KnowledgeEntityLink.entity_type.in_(["equipment", "site"]))
    shared_entities = await session.scalars(
        select(KnowledgeEntityLink.knowledge_item_id).distinct().where(
            KnowledgeEntityLink.entity_type.in_(["equipment", "site"]),
            KnowledgeEntityLink.entity_key.in_(my_entities),
            KnowledgeEntityLink.knowledge_item_id != item_id,
            KnowledgeEntityLink.knowledge_item_id.in_(allowed))
    )
    for other_id in {*shared, *shared_entities}:
        prev = found.get(other_id)
        found[other_id] = Candidate(other_id, prev.similarity if prev else None, True)

    # Shared identifiers first, then by similarity.
    ranked = sorted(found.values(), key=lambda c: (not c.shared_identifier, -(c.similarity or 0)))
    return ranked[:limit]
