"""Consolidate one knowledge item: compare it with a few nominated candidates, store the
validated relationships, and update group membership and the group summary.

Rules that keep groups trustworthy:
- An item joins a group only if it is strongly related (GROUPING_TYPES) to EVERY member,
  so A~B and B~C never put A and C together on their own (no transitive grouping).
- An item that qualifies for two groups is ambiguous and stays ungrouped; an item that is
  strongly related to a grouped item but does not fit that group also stays ungrouped. Its
  relationships remain visible as suggestions.
- Originals are never modified; groups/relationships are derived data.
- Gemini failures keep everything already saved and mark the item for retry.

All work runs under one Postgres advisory transaction lock, so concurrent consolidations
(API process, Slack worker, backfill) are serialized.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import delete, exists, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.consolidation_schema import GroupSummaryDraft, PairComparison
from app.ai.gemini import GeminiClient, GeminiError
from app.core.config import Settings
from app.models import (
    KnowledgeChunk,
    KnowledgeConsolidationState,
    KnowledgeGroup,
    KnowledgeGroupMember,
    KnowledgeItem,
    KnowledgeRelationship,
)
from app.services.consolidation.candidates import eligible_items, find_candidates
from app.services.consolidation.cases import Case, group_fingerprint, load_cases, pair_fingerprint
from app.services.consolidation.prompts import (
    COMPARE_INSTRUCTION,
    SUMMARY_INSTRUCTION,
    compare_contents,
    summary_contents,
)
from app.services.consolidation.validation import (
    CONFLICT_TYPES,
    GROUPING_TYPES,
    validate_comparison,
    validate_summary,
)

logger = logging.getLogger(__name__)

LOCK_KEY = 6_210_042  # pg_advisory_xact_lock id shared by every consolidation run

Status = Literal["done", "retry", "skipped", "unchanged", "missing"]


@dataclass(frozen=True)
class ConsolidationConfig:
    candidate_limit: int = 6
    min_similarity: float = 0.6
    max_group_size: int = 12

    @classmethod
    def from_settings(cls, settings: Settings) -> "ConsolidationConfig":
        return cls(settings.consolidation_candidate_limit, settings.consolidation_min_similarity,
                   settings.consolidation_max_group_size)


@dataclass
class ConsolidationOutcome:
    knowledge_id: uuid.UUID
    status: Status
    compared: int = 0  # Gemini pair comparisons made
    reused: int = 0  # unchanged pairs not re-sent to Gemini
    related: int = 0  # relationships other than "unrelated" involving this item
    group_id: uuid.UUID | None = None
    group_action: str | None = None  # created | joined | kept | left | ambiguous
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def _key(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


def _strong(row: KnowledgeRelationship | None) -> bool:
    return row is not None and row.relationship_type in GROUPING_TYPES


class _Run:
    def __init__(self, session: AsyncSession, gemini: GeminiClient, config: ConsolidationConfig,
                 force: bool) -> None:
        self.session, self.gemini, self.config, self.force = session, gemini, config, force
        self.cases: dict[uuid.UUID, Case | None] = {}
        self.eligible: set[uuid.UUID] | None = None
        self.done_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.budget = config.candidate_limit + config.max_group_size  # Gemini comparisons per run
        self.compared = self.reused = 0
        self.gemini_error: str | None = None
        self.incomplete = False  # some decision could not be made; retry later
        self.touched: set[uuid.UUID] = set()
        self.notes: list[str] = []

    # ---- loading --------------------------------------------------------------------------

    async def is_eligible(self, item_id: uuid.UUID) -> bool:
        if self.eligible is None:
            self.eligible = set(await self.session.scalars(eligible_items()))
        return item_id in self.eligible

    async def case(self, item_id: uuid.UUID) -> Case | None:
        """A usable case: exists, eligible, and has at least one evidence message."""
        if item_id not in self.cases:
            loaded = (await load_cases(self.session, [item_id])).get(item_id)
            ok = loaded is not None and loaded.evidence and await self.is_eligible(item_id)
            self.cases[item_id] = loaded if ok else None
        return self.cases[item_id]

    async def members(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        return list(await self.session.scalars(
            select(KnowledgeGroupMember.knowledge_item_id)
            .where(KnowledgeGroupMember.group_id == group_id)
            .order_by(KnowledgeGroupMember.created_at, KnowledgeGroupMember.knowledge_item_id)))

    async def membership(self, item_id: uuid.UUID) -> KnowledgeGroupMember | None:
        return await self.session.scalar(
            select(KnowledgeGroupMember).where(KnowledgeGroupMember.knowledge_item_id == item_id))

    # ---- pair comparison ------------------------------------------------------------------

    async def relationship(self, a: Case, b: Case) -> KnowledgeRelationship | None:
        """The current, validated relationship of a pair; compares with Gemini when there is
        none or either item changed since. None means unknown (comparison not possible now)."""
        source, target = (a, b) if a.id < b.id else (b, a)
        key = (source.id, target.id)
        row = await self.session.scalar(select(KnowledgeRelationship).where(
            KnowledgeRelationship.source_knowledge_id == key[0],
            KnowledgeRelationship.target_knowledge_id == key[1]))
        fingerprint = pair_fingerprint(source, target)
        fresh = row is not None and row.pair_fingerprint == fingerprint
        if fresh and (not self.force or key in self.done_pairs):
            if key not in self.done_pairs:
                self.reused += 1
                self.done_pairs.add(key)
            return row
        if self.gemini_error is not None or self.budget <= 0:
            self.incomplete = True
            return None

        self.budget -= 1
        first_view, first_payload = source.view("A")
        second_view, second_payload = target.view("B")
        try:
            raw = await self.gemini.generate_structured(
                system_instruction=COMPARE_INSTRUCTION,
                contents=compare_contents(first_payload, second_payload),
                schema=PairComparison,
            )
        except GeminiError as exc:
            self.gemini_error = str(exc) or type(exc).__name__
            self.incomplete = True
            return None
        self.compared += 1
        self.done_pairs.add(key)
        valid = validate_comparison(raw, first_view, second_view)
        if row is None:
            row = KnowledgeRelationship(source_knowledge_id=key[0], target_knowledge_id=key[1])
            self.session.add(row)
        row.relationship_type = valid.relationship_type
        row.outcome_comparison = valid.outcome_comparison
        row.explanation = valid.explanation
        row.shared_symptoms = valid.shared_symptoms
        row.shared_equipment = valid.shared_equipment
        row.conditions = [{"field": c["field"], "source_value": c["first_value"],
                           "target_value": c["second_value"]} for c in valid.conditions]
        row.unknown_conditions = valid.unknown_conditions
        row.source_evidence_ids = [str(i) for i in valid.first_evidence_ids]
        row.target_evidence_ids = [str(i) for i in valid.second_evidence_ids]
        row.validation_notes = valid.notes
        row.model_name = self.gemini.model
        row.pair_fingerprint = fingerprint
        await self.session.flush()
        return row

    async def fits(self, case: Case, member_ids: list[uuid.UUID]) -> bool | None:
        """Strongly related to every (usable) member? None if some pair is unknown."""
        unknown = False
        for member_id in member_ids:
            if member_id == case.id:
                continue
            other = await self.case(member_id)
            if other is None:
                continue  # removed/ineligible member; cleaned up when it is consolidated
            row = await self.relationship(case, other)
            if row is None:
                unknown = True
            elif not _strong(row):
                return False
        return None if unknown else True

    # ---- groups ---------------------------------------------------------------------------

    async def leave_group(self, item_id: uuid.UUID) -> uuid.UUID | None:
        membership = await self.membership(item_id)
        if membership is None:
            return None
        group_id = membership.group_id
        await self.session.delete(membership)
        await self.session.flush()
        self.touched.add(group_id)
        return group_id

    async def update_group(self, case: Case, candidate_ids: list[uuid.UUID]) -> tuple[str | None, uuid.UUID | None]:
        left = None
        membership = await self.membership(case.id)
        if membership is not None:
            members = await self.members(membership.group_id)
            fit = await self.fits(case, members)
            if fit is not False:
                self.touched.add(membership.group_id)  # content may have changed: refresh summary
                return "kept", membership.group_id
            left = await self.leave_group(case.id)
            self.notes.append("No longer strongly related to every group member; left the group.")

        # Strong neighbours: nominated candidates plus anything previously related.
        related = await self.session.execute(select(
            KnowledgeRelationship.source_knowledge_id, KnowledgeRelationship.target_knowledge_id
        ).where(or_(KnowledgeRelationship.source_knowledge_id == case.id,
                    KnowledgeRelationship.target_knowledge_id == case.id)))
        neighbour_ids = list(dict.fromkeys(
            candidate_ids + [s if t == case.id else t for s, t in related.all()]))
        strong: list[uuid.UUID] = []
        for other_id in neighbour_ids:
            other = await self.case(other_id)
            if other is not None and _strong(await self.relationship(case, other)):
                strong.append(other_id)
        if not strong:
            return ("left" if left else None), None

        grouped: dict[uuid.UUID, list[uuid.UUID]] = {}
        for other_id in strong:
            m = await self.membership(other_id)
            if m is not None and m.group_id != left:
                grouped.setdefault(m.group_id, await self.members(m.group_id))
        if grouped:
            qualifying = []
            for group_id, members in grouped.items():
                if len(members) < self.config.max_group_size and await self.fits(case, members) is True:
                    qualifying.append(group_id)
            if len(qualifying) == 1:
                self.session.add(KnowledgeGroupMember(group_id=qualifying[0], knowledge_item_id=case.id))
                await self.session.flush()
                self.touched.add(qualifying[0])
                return "joined", qualifying[0]
            self.notes.append(
                "Related to several groups; left ungrouped." if qualifying else
                "Related to grouped knowledge but not to every member of its group; left ungrouped.")
            return "ambiguous", None

        # Only ungrouped neighbours: start a group with the strongest one; the others join
        # only if they are strongly related to every member.
        group = KnowledgeGroup(title=case.item.title[:500])
        self.session.add(group)
        await self.session.flush()
        members = [case.id]
        for other_id in strong:
            if len(members) >= self.config.max_group_size:
                break
            other = await self.case(other_id)
            if other is not None and (len(members) == 1 or await self.fits(other, members) is True):
                members.append(other_id)
        for member_id in members:
            self.session.add(KnowledgeGroupMember(group_id=group.id, knowledge_item_id=member_id))
        await self.session.flush()
        self.touched.add(group.id)
        return "created", group.id

    async def refresh_summary(self, group_id: uuid.UUID) -> None:
        group = await self.session.get(KnowledgeGroup, group_id)
        if group is None:
            return
        member_ids = await self.members(group_id)
        cases = [c for c in [await self.case(m) for m in member_ids] if c is not None]
        if len(member_ids) < 2 or len(cases) < 2:
            await self.session.delete(group)  # a group of one is not a group
            await self.session.flush()
            return
        fingerprint = group_fingerprint(cases)
        if group.summary_fingerprint == fingerprint and not self.force:
            return
        if self.gemini_error is not None:
            self.incomplete = True
            return

        labels = {f"K{i}": c.id for i, c in enumerate(cases, start=1)}
        label_of = {v: k for k, v in labels.items()}
        payloads = {}
        for label, c in zip(labels, cases, strict=True):
            payload = c.view("x")[1]
            payload.pop("messages")
            payload["key_messages"] = [e["text"] for e in c.evidence[:6]]
            if c.feedback is not None:
                payload["troubleshooting_feedback"] = c.feedback_payload()
            payloads[label] = payload
        rows = list(await self.session.scalars(select(KnowledgeRelationship).where(
            KnowledgeRelationship.source_knowledge_id.in_(labels.values()),
            KnowledgeRelationship.target_knowledge_id.in_(labels.values()))))
        relations = [
            f"{label_of[r.source_knowledge_id]}-{label_of[r.target_knowledge_id]}: {r.relationship_type}"
            + (f" ({r.explanation})" if r.explanation else "")
            + "".join(f"; {c['field']}: {c['source_value'] or 'unknown'} vs {c['target_value'] or 'unknown'}"
                      for c in r.conditions)
            for r in rows if r.relationship_type != "unrelated"]
        try:
            draft = await self.gemini.generate_structured(
                system_instruction=SUMMARY_INSTRUCTION, contents=summary_contents(payloads, relations),
                schema=GroupSummaryDraft)
        except GeminiError as exc:
            self.gemini_error = str(exc) or type(exc).__name__
            self.incomplete = True
            return
        valid = validate_summary(draft, labels, "\n".join(c.corpus(include_feedback=True) for c in cases))
        data = valid.to_json()
        data.update({
            "case_count": len(cases),
            # Independent conversations, counted server-side (not by Gemini).
            "independent_conversations": len({c.thread_id or c.id for c in cases}),
            "conflict_count": sum(r.relationship_type in CONFLICT_TYPES for r in rows),
            "feedback_sessions": sum(c.feedback.sessions for c in cases if c.feedback),
            "review_status": "unreviewed",  # generated summaries are never approved knowledge
            "generated_at": datetime.now(UTC).isoformat(),
        })
        group.title = valid.title
        group.summary = valid.shared_problem
        group.summary_data = data
        group.summary_fingerprint = fingerprint
        group.summary_model = self.gemini.model
        await self.session.flush()


async def _save_state(session: AsyncSession, item_id: uuid.UUID, status: str, fingerprint: str | None,
                      error: str | None) -> None:
    now = datetime.now(UTC)
    values: dict[str, Any] = {"status": status, "fingerprint": fingerprint, "last_error": error,
                              "consolidated_at": now if status == "done" else None}
    await session.execute(
        insert(KnowledgeConsolidationState).values(knowledge_item_id=item_id, **values)
        .on_conflict_do_update(index_elements=["knowledge_item_id"], set_={**values, "updated_at": now}))


async def consolidate_item(session: AsyncSession, item_id: uuid.UUID, gemini: GeminiClient,
                           config: ConsolidationConfig | None = None, *, force: bool = False) -> ConsolidationOutcome:
    config = config or ConsolidationConfig()
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
    run = _Run(session, gemini, config, force)

    if await session.get(KnowledgeItem, item_id) is None:
        await session.commit()  # releases the lock; nothing was written (rollback would expire callers' objects)
        return ConsolidationOutcome(item_id, "missing")
    case = await run.case(item_id)
    if case is None:
        # Not eligible (source disabled, rejected) or no evidence: never grouped.
        left = await run.leave_group(item_id)
        for group_id in run.touched:
            await run.refresh_summary(group_id)
        await _save_state(session, item_id, "skipped", None, "Not eligible or no evidence messages.")
        await session.commit()
        return ConsolidationOutcome(item_id, "skipped", group_action="left" if left else None)

    state = await session.get(KnowledgeConsolidationState, item_id)
    if state is not None and state.status == "done" and state.fingerprint == case.fingerprint and not force:
        await session.commit()  # releases the lock; nothing was written (rollback would expire callers' objects)
        return ConsolidationOutcome(item_id, "unchanged")

    has_embedding = bool(await session.scalar(select(exists().where(
        KnowledgeChunk.knowledge_item_id == item_id, KnowledgeChunk.embedding.is_not(None)))))
    candidates = await find_candidates(session, item_id, limit=config.candidate_limit,
                                       min_similarity=config.min_similarity)
    candidate_ids = []
    for candidate in candidates:
        other = await run.case(candidate.knowledge_id)
        if other is not None:
            candidate_ids.append(other.id)
            await run.relationship(case, other)

    action, group_id = await run.update_group(case, candidate_ids)
    for touched in sorted(run.touched):
        await run.refresh_summary(touched)
    if group_id is not None and await session.get(KnowledgeGroup, group_id) is None:
        group_id = None

    related = await session.scalar(select(func.count()).select_from(KnowledgeRelationship).where(
        or_(KnowledgeRelationship.source_knowledge_id == item_id,
            KnowledgeRelationship.target_knowledge_id == item_id),
        KnowledgeRelationship.relationship_type != "unrelated"))

    error = run.gemini_error
    if not has_embedding:
        error = error or "Embedding pending: only shared identifiers were checked."
    status: Status = "retry" if (run.incomplete or not has_embedding) else "done"
    await _save_state(session, item_id, status, case.fingerprint, error)
    await session.commit()
    return ConsolidationOutcome(item_id, status, compared=run.compared, reused=run.reused,
                                related=related or 0, group_id=group_id, group_action=action,
                                error=error, notes=run.notes)


async def refresh_group_for_item(session: AsyncSession, item_id: uuid.UUID, gemini: GeminiClient,
                                 config: ConsolidationConfig | None = None) -> str:
    """After new troubleshooting feedback: regenerate the summary of the item's group only
    (no pair comparisons; feedback does not change what the cases say). Returns
    "ungrouped", "unchanged", "refreshed" or "retry" (summary stays marked as outdated)."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
    run = _Run(session, gemini, config or ConsolidationConfig(), force=False)
    membership = await run.membership(item_id)
    if membership is None:
        await session.commit()
        return "ungrouped"
    group_id = membership.group_id
    group = await session.get(KnowledgeGroup, group_id)
    before = group.summary_fingerprint if group else None
    await run.refresh_summary(group_id)
    group = await session.get(KnowledgeGroup, group_id)
    after = group.summary_fingerprint if group else None
    await session.commit()
    if run.incomplete:
        return "retry"
    return "refreshed" if after != before else "unchanged"


async def items_needing_consolidation(session: AsyncSession, *, force: bool = False) -> list[uuid.UUID]:
    """Eligible items never consolidated, marked for retry, or changed since (backfill)."""
    ids = list(await session.scalars(
        select(KnowledgeItem.id).where(KnowledgeItem.id.in_(eligible_items()))
        .order_by(KnowledgeItem.created_at, KnowledgeItem.id)))
    if force:
        return ids
    states = {s.knowledge_item_id: s for s in await session.scalars(select(KnowledgeConsolidationState))}
    cases = await load_cases(session, [i for i in ids if i in states and states[i].status == "done"])
    return [i for i in ids if i not in states or states[i].status != "done"
            or (i in cases and cases[i].fingerprint != states[i].fingerprint)]


async def remove_ineligible_memberships(session: AsyncSession) -> int:
    """Drop group members whose source was disabled or that were rejected (no Gemini needed)."""
    result = await session.execute(delete(KnowledgeGroupMember).where(
        KnowledgeGroupMember.knowledge_item_id.not_in(eligible_items())))
    await prune_small_groups(session)
    await session.commit()
    return result.rowcount or 0


async def prune_small_groups(session: AsyncSession) -> int:
    """Delete groups left with fewer than two members (e.g. after a demo reset). Caller commits."""
    kept = select(KnowledgeGroupMember.group_id).group_by(KnowledgeGroupMember.group_id).having(
        func.count() >= 2)
    result = await session.execute(delete(KnowledgeGroup).where(KnowledgeGroup.id.not_in(kept)))
    return result.rowcount or 0
