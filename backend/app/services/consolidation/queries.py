"""Read side of consolidation: related knowledge and groups, limited to visible knowledge
(items from enabled sources that an expert has not rejected)."""

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeGroup, KnowledgeGroupMember, KnowledgeRelationship, Message
from app.schemas.consolidation import (
    CaseRef,
    ConditionRead,
    EvidenceRef,
    GroupBrief,
    GroupDetail,
    GroupMemberRead,
    RelatedKnowledge,
    RelationshipRead,
    SolutionRead,
)
from app.services.consolidation.candidates import eligible_items
from app.services.consolidation.cases import Case, group_fingerprint, load_cases

# Order for display: grouping-strength relationships and conflicts before weak suggestions.
TYPE_ORDER = {
    "supporting_evidence": 0, "same_problem": 1, "same_problem_different_conditions": 2,
    "different_outcome": 3, "potentially_conflicting": 4, "related_symptoms": 5, "unrelated": 9,
}


def _case_ref(case: Case) -> dict[str, Any]:
    item = case.item
    return {"id": item.id, "title": item.title, "resolution_status": item.resolution_status,
            "approval_status": item.approval_status, "conversation": case.conversation,
            "source_name": case.source_name, "thread_id": case.thread_id}


async def _visible(session: AsyncSession) -> set[uuid.UUID]:
    return set(await session.scalars(eligible_items()))


async def _evidence(session: AsyncSession, ids: list[str], case: Case) -> list[EvidenceRef]:
    wanted = {uuid.UUID(i) for i in ids}
    by_id = {e["message_id"]: e for e in case.evidence}
    urls = dict((await session.execute(
        select(Message.id, Message.source_url).where(Message.id.in_(wanted)))).all()) if wanted else {}
    return [EvidenceRef(message_id=m, author=by_id[m]["author"], sent_at=by_id[m]["sent_at"],
                        excerpt=by_id[m]["text"], source_url=urls.get(m))
            for m in (uuid.UUID(i) for i in ids) if m in by_id]


async def _relationship_reads(session: AsyncSession, rows: list[KnowledgeRelationship],
                              cases: dict[uuid.UUID, Case]) -> list[RelationshipRead]:
    out = []
    for r in sorted(rows, key=lambda r: (TYPE_ORDER.get(r.relationship_type, 8), str(r.id))):
        source, target = cases.get(r.source_knowledge_id), cases.get(r.target_knowledge_id)
        if source is None or target is None or r.relationship_type == "unrelated":
            continue
        out.append(RelationshipRead(
            id=r.id, relationship_type=r.relationship_type, outcome_comparison=r.outcome_comparison,
            explanation=r.explanation, source=CaseRef(**_case_ref(source)), target=CaseRef(**_case_ref(target)),
            shared_symptoms=r.shared_symptoms, shared_equipment=r.shared_equipment,
            conditions=[ConditionRead(**c) for c in r.conditions], unknown_conditions=r.unknown_conditions,
            source_evidence=await _evidence(session, r.source_evidence_ids, source),
            target_evidence=await _evidence(session, r.target_evidence_ids, target),
            validation_notes=r.validation_notes, model_name=r.model_name, updated_at=r.updated_at,
        ))
    return out


async def _visible_members(session: AsyncSession, group_ids: list[uuid.UUID],
                           visible: set[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
    members: dict[uuid.UUID, list[uuid.UUID]] = {g: [] for g in group_ids}
    rows = await session.execute(
        select(KnowledgeGroupMember.group_id, KnowledgeGroupMember.knowledge_item_id)
        .where(KnowledgeGroupMember.group_id.in_(group_ids))
        .order_by(KnowledgeGroupMember.created_at, KnowledgeGroupMember.knowledge_item_id))
    for group_id, item_id in rows:
        if item_id in visible:
            members[group_id].append(item_id)
    return members


def _brief(group: KnowledgeGroup, cases: list[Case]) -> dict[str, Any]:
    data = group.summary_data or {}
    solutions = data.get("solutions") or []
    pending = not group.summary_fingerprint or group.summary_fingerprint != group_fingerprint(cases)
    return {
        "id": group.id, "title": group.title, "summary": group.summary, "case_count": len(cases),
        # Counted from the visible members, so hidden knowledge never inflates the number.
        "independent_conversations": len({c.thread_id or c.id for c in cases}),
        "solution_count": len(solutions),
        "successful_paths": sum(s.get("outcome") == "successful" for s in solutions),
        "conflict_count": int(data.get("conflict_count") or 0),
        "summary_pending": pending, "updated_at": group.updated_at,
    }


async def group_briefs(session: AsyncSession, group_ids: list[uuid.UUID],
                       visible: set[uuid.UUID] | None = None) -> dict[uuid.UUID, GroupBrief]:
    """Briefs of groups that still have at least two visible members."""
    if not group_ids:
        return {}
    visible = visible if visible is not None else await _visible(session)
    members = await _visible_members(session, group_ids, visible)
    cases = await load_cases(session, [m for ms in members.values() for m in ms])
    groups = await session.scalars(select(KnowledgeGroup).where(KnowledgeGroup.id.in_(group_ids)))
    out = {}
    for group in groups:
        group_cases = [cases[m] for m in members[group.id] if m in cases]
        if len(group_cases) >= 2:
            out[group.id] = GroupBrief(**_brief(group, group_cases))
    return out


async def groups_for_items(session: AsyncSession, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, GroupBrief]:
    """item id -> brief of its group (search results)."""
    rows = (await session.execute(select(KnowledgeGroupMember.knowledge_item_id, KnowledgeGroupMember.group_id)
                                  .where(KnowledgeGroupMember.knowledge_item_id.in_(item_ids)))).all()
    briefs = await group_briefs(session, list({g for _, g in rows}))
    return {item: briefs[g] for item, g in rows if g in briefs}


async def list_groups(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[GroupBrief], int]:
    ids = list(await session.scalars(select(KnowledgeGroup.id).order_by(KnowledgeGroup.updated_at.desc())))
    briefs = await group_briefs(session, ids)
    ordered = [briefs[i] for i in ids if i in briefs]
    return ordered[offset: offset + limit], len(ordered)


async def get_group(session: AsyncSession, group_id: uuid.UUID) -> GroupDetail | None:
    group = await session.get(KnowledgeGroup, group_id)
    if group is None:
        return None
    visible = await _visible(session)
    member_ids = (await _visible_members(session, [group_id], visible))[group_id]
    cases = await load_cases(session, member_ids)
    ordered = [cases[m] for m in member_ids if m in cases]
    if len(ordered) < 2:
        return None  # only hidden members left: not visible to the caller
    data = group.summary_data or {}
    visible_ids = {str(c.id) for c in ordered}
    solutions = []
    for s in data.get("solutions") or []:
        ids = [uuid.UUID(k) for k in s.get("knowledge_ids", []) if k in visible_ids]
        if ids:  # paths reported only by hidden knowledge are not shown
            solutions.append(SolutionRead(description=s["description"], outcome=s["outcome"],
                                          conditions=s.get("conditions", []), knowledge_ids=ids))
    members = [GroupMemberRead(
        **_case_ref(c), problem_description=c.item.problem_description, resolution=c.item.resolution,
        equipment=sorted(e.equipment_identifier for e in c.item.equipment),
        applicability_conditions=c.item.applicability_conditions, evidence_count=len(c.evidence),
    ) for c in ordered]
    brief = _brief(group, ordered)
    brief["solution_count"] = len(solutions)
    brief["successful_paths"] = sum(s.outcome == "successful" for s in solutions)
    return GroupDetail(
        **brief, shared_problem=data.get("shared_problem"), shared_symptoms=data.get("shared_symptoms", []),
        known_environment=data.get("known_environment", []), solutions=solutions,
        failed_attempts=data.get("failed_attempts", []), contradictions=data.get("contradictions", []),
        missing_information=data.get("missing_information", []), summary_model=group.summary_model,
        generated_at=data.get("generated_at"), members=members,
    )


async def group_relationships(session: AsyncSession, group_id: uuid.UUID) -> list[RelationshipRead] | None:
    if await session.get(KnowledgeGroup, group_id) is None:
        return None
    visible = await _visible(session)
    member_ids = (await _visible_members(session, [group_id], visible))[group_id]
    rows = list(await session.scalars(select(KnowledgeRelationship).where(
        KnowledgeRelationship.source_knowledge_id.in_(member_ids),
        KnowledgeRelationship.target_knowledge_id.in_(member_ids))))
    return await _relationship_reads(session, rows, await load_cases(session, member_ids))


async def related_knowledge(session: AsyncSession, item_id: uuid.UUID) -> RelatedKnowledge | None:
    visible = await _visible(session)
    if item_id not in visible:
        return None
    rows = list(await session.scalars(select(KnowledgeRelationship).where(
        or_(KnowledgeRelationship.source_knowledge_id == item_id,
            KnowledgeRelationship.target_knowledge_id == item_id),
        KnowledgeRelationship.relationship_type != "unrelated")))
    others = {r.target_knowledge_id if r.source_knowledge_id == item_id else r.source_knowledge_id for r in rows}
    cases = await load_cases(session, [item_id, *[o for o in others if o in visible]])
    group_id = await session.scalar(select(KnowledgeGroupMember.group_id).where(
        KnowledgeGroupMember.knowledge_item_id == item_id))
    briefs = await group_briefs(session, [group_id], visible) if group_id else {}
    return RelatedKnowledge(knowledge_id=item_id, group=briefs.get(group_id) if group_id else None,
                            relationships=await _relationship_reads(session, rows, cases))


async def group_count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(KnowledgeGroup)) or 0)
