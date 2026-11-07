"""Server-side validation of a Gemini guide draft.

Graph rules (MVP): a directed acyclic graph with exactly one start node, every node reachable
from it, no dangling or self edges, unique answers per node, terminal nodes (resolution,
escalation) without outgoing edges and every other node with at least one.

Evidence rules: only knowledge/evidence labels from the retrieved context are accepted.
Every diagnostic, recommendation and resolution step must cite at least one valid message.
Approval status and support level are derived from the knowledge, never from the model.
"""

import uuid
from dataclasses import dataclass, field

from app.ai.guide_schema import GuideDraft
from app.models.enums import (
    ApprovalStatus,
    EvidenceType,
    GuideNodeType,
    ResolutionStatus,
    SupportLevel,
)

EVIDENCE_REQUIRED = {GuideNodeType.DIAGNOSTIC, GuideNodeType.RECOMMENDATION, GuideNodeType.RESOLUTION}
TERMINAL = {GuideNodeType.RESOLUTION, GuideNodeType.ESCALATION}
MAX_NODES = 30


class GuideValidationError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class ContextEvidence:
    message_id: uuid.UUID
    knowledge_id: uuid.UUID
    evidence_type: EvidenceType


@dataclass(frozen=True)
class ContextKnowledge:
    id: uuid.UUID
    resolution_status: ResolutionStatus
    approval_status: ApprovalStatus


@dataclass
class GuideContext:
    """What retrieval returned, addressable by the labels given to the model."""

    knowledge: dict[str, ContextKnowledge] = field(default_factory=dict)  # "K1" -> ...
    evidence: dict[str, ContextEvidence] = field(default_factory=dict)  # "E1" -> ...


@dataclass
class ValidNode:
    key: str
    position: int
    node_type: GuideNodeType
    title: str
    description: str | None
    question: str | None
    expected_answers: list[str]
    applicability_conditions: list[str]
    knowledge_ids: list[uuid.UUID]
    evidence: list[ContextEvidence]
    approval_status: ApprovalStatus | None
    support_level: SupportLevel
    requires_manual_verification: bool
    conflict_note: str | None


@dataclass
class ValidEdge:
    source: str
    target: str
    answer_label: str
    condition: str | None


@dataclass
class ValidGuide:
    title: str
    summary: str
    nodes: list[ValidNode]
    edges: list[ValidEdge]
    knowledge_ids: list[uuid.UUID]
    conflicts: list[str]
    uncertainties: list[str]
    notes: list[str]


def _clean(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


def _derive_status(items: list[ContextKnowledge], conflict: bool) -> tuple[ApprovalStatus | None, SupportLevel]:
    if not items:
        return None, SupportLevel.NONE
    approvals = {k.approval_status for k in items}
    if ApprovalStatus.REJECTED in approvals:
        approval = ApprovalStatus.REJECTED
    elif approvals == {ApprovalStatus.APPROVED}:
        approval = ApprovalStatus.APPROVED
    else:
        approval = ApprovalStatus.UNREVIEWED
    if conflict:
        return approval, SupportLevel.CONFLICTING
    if approval is ApprovalStatus.APPROVED:
        return approval, SupportLevel.APPROVED
    if any(k.resolution_status is ResolutionStatus.CONFIRMED_IN_CONVERSATION for k in items):
        return approval, SupportLevel.CONFIRMED_IN_CONVERSATION
    return approval, SupportLevel.SUGGESTED


def _has_cycle(keys: list[str], children: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}  # 1 = visiting, 2 = done

    def visit(node: str) -> bool:
        state[node] = 1
        for child in children.get(node, []):
            if state.get(child) == 1 or (state.get(child) is None and visit(child)):
                return True
        state[node] = 2
        return False

    return any(state.get(k) is None and visit(k) for k in keys)


def validate_guide(draft: GuideDraft, context: GuideContext) -> ValidGuide:
    problems: list[str] = []
    notes: list[str] = []

    # ---- nodes ----
    if not 2 <= len(draft.nodes) <= MAX_NODES:
        raise GuideValidationError([f"A guide needs between 2 and {MAX_NODES} steps."])
    keys = [n.id.strip() for n in draft.nodes]
    if len(set(keys)) != len(keys) or any(not k for k in keys):
        raise GuideValidationError(["Step ids must be unique and non-empty."])
    starts = [n for n in draft.nodes if n.node_type == "start"]
    if len(starts) != 1:
        problems.append(f"Exactly one start step is required (found {len(starts)}).")

    # ---- edges ----
    children: dict[str, list[str]] = {k: [] for k in keys}
    edges: list[ValidEdge] = []
    seen_answers: set[tuple[str, str]] = set()
    for edge in draft.edges:
        source, target, label = edge.source.strip(), edge.target.strip(), edge.answer_label.strip()
        if source not in children or target not in children:
            problems.append(f"Edge {source}->{target} points to a step that does not exist.")
            continue
        if source == target:
            problems.append(f"Step {source} links to itself.")
            continue
        if not label:
            problems.append(f"Edge {source}->{target} has no answer label.")
            continue
        if (source, label.lower()) in seen_answers:
            problems.append(f"Step {source} has the answer '{label}' twice.")
            continue
        seen_answers.add((source, label.lower()))
        children[source].append(target)
        edges.append(ValidEdge(source, target, label[:100], _clean(edge.condition)))

    if _has_cycle(keys, children):
        problems.append("The steps form a loop; a guide must not loop back.")
    if len(starts) == 1:
        reachable, frontier = set(), [starts[0].id.strip()]
        while frontier:
            node = frontier.pop()
            if node not in reachable:
                reachable.add(node)
                frontier.extend(children[node])
        unreachable = [k for k in keys if k not in reachable]
        if unreachable:
            problems.append(f"Steps not reachable from the start: {', '.join(unreachable)}.")

    # ---- per-node rules and evidence ----
    nodes: list[ValidNode] = []
    used_knowledge: list[uuid.UUID] = []
    for position, draft_node in enumerate(draft.nodes):
        key = draft_node.id.strip()
        node_type = GuideNodeType(draft_node.node_type)
        outgoing = [e for e in edges if e.source == key]
        if node_type in TERMINAL and outgoing:
            problems.append(f"{node_type.value.title()} step {key} must be an end point.")
        if node_type not in TERMINAL and not outgoing:
            problems.append(f"Step {key} is a dead end; it needs a next step, a resolution or an escalation.")
        if node_type is GuideNodeType.QUESTION:
            if not _clean(draft_node.question):
                problems.append(f"Question step {key} has no question.")
            if len(outgoing) < 2:
                problems.append(f"Question step {key} needs at least two answers.")

        evidence: list[ContextEvidence] = []
        for ref in draft_node.evidence_refs:
            item = context.evidence.get(ref.strip())
            if item is None:
                notes.append(f"Ignored unknown evidence reference '{ref}' in step {key}.")
            # One message can carry several evidence roles (labels); cite each message once.
            elif all(e.message_id != item.message_id for e in evidence):
                evidence.append(item)
        knowledge_ids: list[uuid.UUID] = []
        for ref in draft_node.knowledge_refs:
            item = context.knowledge.get(ref.strip())
            if item is None:
                notes.append(f"Ignored unknown knowledge reference '{ref}' in step {key}.")
            elif item.id not in knowledge_ids:
                knowledge_ids.append(item.id)
        for e in evidence:  # evidence implies its knowledge item
            if e.knowledge_id not in knowledge_ids:
                knowledge_ids.append(e.knowledge_id)

        if node_type in EVIDENCE_REQUIRED and not evidence:
            problems.append(f"{node_type.value.title()} step {key} cites no valid source message.")

        items = [k for k in context.knowledge.values() if k.id in knowledge_ids]
        conflict = _clean(draft_node.conflict_note)
        approval, support = _derive_status(items, conflict is not None)
        if node_type not in EVIDENCE_REQUIRED and support is not SupportLevel.CONFLICTING:
            # Navigation steps (start, question, escalation) make no technical claim: any
            # cited messages are shown as context, but they get no "worked"/"approved" label.
            approval, support = None, SupportLevel.NONE
        for k in knowledge_ids:
            if k not in used_knowledge:
                used_knowledge.append(k)

        nodes.append(ValidNode(
            key=key,
            position=position,
            node_type=node_type,
            title=draft_node.title.strip()[:300] or node_type.value.title(),
            description=_clean(draft_node.description),
            question=_clean(draft_node.question),
            expected_answers=[e.answer_label for e in outgoing],  # derived from real branches
            applicability_conditions=[c.strip() for c in draft_node.applicability_conditions if c.strip()],
            knowledge_ids=knowledge_ids,
            evidence=evidence,
            approval_status=approval,
            support_level=support,
            # Anything not expert-approved must be verified by the engineer; the model cannot waive it.
            requires_manual_verification=node_type in EVIDENCE_REQUIRED and approval is not ApprovalStatus.APPROVED,
            conflict_note=conflict,
        ))

    if not any(n.node_type in TERMINAL for n in nodes):
        problems.append("The guide needs at least one resolution or escalation end point.")
    if problems:
        raise GuideValidationError(problems)

    return ValidGuide(
        title=draft.title.strip()[:500] or "Troubleshooting guide",
        summary=draft.summary.strip(),
        nodes=nodes,
        edges=edges,
        knowledge_ids=used_knowledge,
        conflicts=[c.strip() for c in draft.conflicts if c.strip()],
        uncertainties=[u.strip() for u in draft.uncertainties if u.strip()],
        notes=notes,
    )
