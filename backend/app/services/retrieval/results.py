"""Turn ranked knowledge item IDs into evidence-backed search results."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ConversationThread, KnowledgeEvidence, KnowledgeItem, Message
from app.schemas.search import EvidenceReference, Ranking, SearchResult
from app.services.retrieval.search import RankedItem

MAX_EXCERPT_CHARS = 600


def _excerpt(message: Message) -> str | None:
    if message.deleted_at is not None:
        return None  # removed at the source: do not show its text any more
    text = message.content.strip()
    return text if len(text) <= MAX_EXCERPT_CHARS else text[: MAX_EXCERPT_CHARS - 1].rstrip() + "…"


def _ranking(entry: RankedItem) -> Ranking:
    matched = [name for name, signal in
               (("semantic", entry.semantic), ("keyword", entry.keyword), ("identifier", entry.identifier))
               if signal is not None]
    return Ranking(
        score=round(entry.score, 6),
        matched_by=matched,
        semantic_rank=entry.semantic.rank if entry.semantic else None,
        semantic_similarity=round(entry.semantic.score, 4) if entry.semantic else None,
        keyword_rank=entry.keyword.rank if entry.keyword else None,
        keyword_score=round(entry.keyword.score, 4) if entry.keyword else None,
        identifier_rank=entry.identifier.rank if entry.identifier else None,
        matched_identifiers=entry.matched_identifiers,
    )


async def build_results(session: AsyncSession, ranked: list[RankedItem]) -> list[SearchResult]:
    if not ranked:
        return []
    items = {
        item.id: item
        for item in await session.scalars(
            select(KnowledgeItem)
            .where(KnowledgeItem.id.in_([r.item_id for r in ranked]))
            .options(
                selectinload(KnowledgeItem.evidence)
                .selectinload(KnowledgeEvidence.message)
                .selectinload(Message.thread)
                .selectinload(ConversationThread.source),
                selectinload(KnowledgeItem.equipment),
                selectinload(KnowledgeItem.incidents),
                selectinload(KnowledgeItem.candidate),
            )
        )
    }

    results = []
    for entry in ranked:
        item = items.get(entry.item_id)
        if item is None:
            continue
        evidence = sorted(item.evidence, key=lambda e: (e.message.sent_at, e.message.external_message_id))
        data = (item.candidate.extracted_data or {}) if item.candidate else {}
        results.append(SearchResult(
            id=item.id,
            title=item.title,
            problem_description=item.problem_description,
            symptoms=item.symptoms or [],
            root_cause=item.root_cause,
            resolution=item.resolution,
            resolution_status=item.resolution_status,
            approval_status=item.approval_status,
            attempted_actions=item.attempted_actions or [],
            applicability_conditions=item.applicability_conditions or [],
            missing_information=data.get("analysis", {}).get("missing_information", []),
            equipment_identifiers=sorted(e.equipment_identifier for e in item.equipment),
            incident_numbers=sorted(i.incident_number for i in item.incidents),
            evidence_status="supported" if evidence else "missing",
            evidence=[
                EvidenceReference(
                    message_id=e.message.id,
                    evidence_type=e.evidence_type,
                    explanation=e.explanation,
                    author=e.message.author_display_name or e.message.author_external_id,
                    sent_at=e.message.sent_at,
                    excerpt=_excerpt(e.message),
                    deleted_at_source=e.message.deleted_at is not None,
                    source_name=e.message.thread.source.name if e.message.thread.source else None,
                    source_type=e.message.thread.source.source_type if e.message.thread.source else None,
                    thread_id=e.message.thread_id,
                    thread_title=e.message.thread.title,
                    source_url=e.message.source_url,
                )
                for e in evidence
            ],
            ranking=_ranking(entry),
            updated_at=item.updated_at,
        ))
    return results

