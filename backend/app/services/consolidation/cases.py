"""Load knowledge items as comparable "cases" (fields + evidence) and fingerprint them."""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ConversationThread, KnowledgeCandidate, KnowledgeEvidence, KnowledgeItem, Message
from app.schemas.feedback import FeedbackSummary
from app.services.consolidation.validation import CaseView
from app.services.feedback.summary import feedback_summaries, summary_text
from app.services.retrieval.indexing import item_chunk_texts

MAX_EXCERPT = 400


@dataclass
class Case:
    item: KnowledgeItem
    thread_id: uuid.UUID | None
    conversation: str | None
    source_name: str | None
    evidence: list[dict[str, Any]] = field(default_factory=list)  # {"message_id","type","author","sent_at","text"}
    fingerprint: str = ""
    # Engineers' troubleshooting feedback (Phase 6C). Not part of `fingerprint`, so new
    # feedback refreshes group summaries without re-comparing pairs.
    feedback: FeedbackSummary | None = None

    @property
    def id(self) -> uuid.UUID:
        return self.item.id

    def corpus(self, *, include_feedback: bool = False) -> str:
        parts = item_chunk_texts(self.item) + [e["text"] for e in self.evidence]
        if include_feedback and self.feedback:
            parts += [f"firmware {b.value}" for b in self.feedback.by_firmware if b.value]
            parts += [b.value for b in self.feedback.by_equipment if b.value]
        return "\n".join(parts)

    def feedback_payload(self) -> dict[str, Any] | None:
        """Aggregated feedback for prompts (counts and conditions only, no free text)."""
        f = self.feedback
        if f is None:
            return None
        return {
            "kind": "self-reported by engineers after guided troubleshooting (not verified, not approval)",
            "summary": summary_text(f),
            "by_firmware": [{"firmware": b.value or "not reported", **b.counts.model_dump()} for b in f.by_firmware],
            "by_equipment": [{"equipment": b.value or "not reported", **b.counts.model_dump()}
                             for b in f.by_equipment],
        }

    def feedback_fingerprint(self) -> str:
        f = self.feedback
        if f is None:
            return ""
        return json.dumps([f.counts.model_dump(), [b.model_dump() for b in f.by_firmware],
                           [b.model_dump() for b in f.by_equipment]], sort_keys=True)

    def view(self, prefix: str) -> tuple[CaseView, dict[str, Any]]:
        """Labelled view for a prompt: evidence becomes A1, A2, ... (or B1, ...)."""
        labels = {f"{prefix}{i}": e["message_id"] for i, e in enumerate(self.evidence, start=1)}
        payload = {
            "title": self.item.title,
            "problem": self.item.problem_description,
            "symptoms": self.item.symptoms,
            "root_cause": self.item.root_cause,
            "resolution": self.item.resolution,
            "resolution_status": self.item.resolution_status.value,
            "approval_status": self.item.approval_status.value,
            "attempted_actions": [{"action": a.get("action"), "outcome": a.get("outcome")}
                                  for a in self.item.attempted_actions or []],
            "applicability_conditions": self.item.applicability_conditions,
            "equipment": sorted(e.equipment_identifier for e in self.item.equipment),
            "knowledge_type": self.item.knowledge_type.value,
            "conversation": self.conversation,
            "first_message_at": self.evidence[0]["sent_at"] if self.evidence else None,
            "last_message_at": self.evidence[-1]["sent_at"] if self.evidence else None,
            "messages": [{"ref": label, "role": e["type"], "author": e["author"], "text": e["text"]}
                         for label, e in zip(labels, self.evidence, strict=True)],
        }
        return CaseView(self.id, labels, self.corpus(), self.latest_at), payload

    @property
    def latest_at(self) -> datetime | None:
        return datetime.fromisoformat(self.evidence[-1]["sent_at"]) if self.evidence else None

    @property
    def earliest_at(self) -> datetime | None:
        return datetime.fromisoformat(self.evidence[0]["sent_at"]) if self.evidence else None


def _fingerprint(item: KnowledgeItem, evidence: list[dict[str, Any]]) -> str:
    payload = [item_chunk_texts(item), sorted(str(e["message_id"]) for e in evidence),
               item.approval_status.value, item.resolution_status.value]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


async def load_cases(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, Case]:
    if not ids:
        return {}
    items = list(await session.scalars(
        select(KnowledgeItem)
        .where(KnowledgeItem.id.in_(ids))
        .options(
            selectinload(KnowledgeItem.evidence).selectinload(KnowledgeEvidence.message)
            .selectinload(Message.thread).selectinload(ConversationThread.source),
            selectinload(KnowledgeItem.equipment),
            selectinload(KnowledgeItem.incidents),
            selectinload(KnowledgeItem.candidate).selectinload(KnowledgeCandidate.thread)
            .selectinload(ConversationThread.source),
        )
        .execution_options(populate_existing=True)
    ))
    cases = {}
    for item in items:
        evidence = []
        seen: set[uuid.UUID] = set()
        for e in sorted(item.evidence, key=lambda e: (e.message.sent_at, e.message.external_message_id)):
            if e.message.deleted_at is not None or e.message_id in seen:
                continue  # deleted at the source, or the same message with another role
            seen.add(e.message_id)
            text = e.message.content.strip()
            evidence.append({
                "message_id": e.message_id, "type": e.evidence_type.value,
                "author": e.message.author_display_name or e.message.author_external_id,
                "sent_at": e.message.sent_at.isoformat(),
                "text": text if len(text) <= MAX_EXCERPT else text[: MAX_EXCERPT - 1] + "…",
            })
        thread = item.candidate.thread if item.candidate else None
        case = Case(item=item, thread_id=thread.id if thread else None,
                    conversation=thread.title if thread else None,
                    source_name=thread.source.name if thread and thread.source else None, evidence=evidence)
        case.fingerprint = _fingerprint(item, evidence)
        cases[item.id] = case
    for item_id, summary in (await feedback_summaries(session, list(cases))).items():
        cases[item_id].feedback = summary
    return cases


def pair_fingerprint(a: Case, b: Case) -> str:
    first, second = sorted([(str(a.id), a.fingerprint), (str(b.id), b.fingerprint)])
    return hashlib.sha256(f"{first}|{second}".encode()).hexdigest()


def group_fingerprint(cases: list[Case]) -> str:
    """Members' content and their feedback: either changing refreshes the group summary."""
    return hashlib.sha256("|".join(sorted(f"{c.id}:{c.fingerprint}:{c.feedback_fingerprint()}"
                                          for c in cases)).encode()).hexdigest()
