"""Hybrid knowledge search: vector similarity + full-text + exact identifiers, fused with RRF.

Each retriever produces its own ranked list of knowledge item IDs. Scores from different
retrievers are never compared directly; Reciprocal Rank Fusion only uses rank positions:

    score(item) = sum over retrievers of weight / (RRF_K + rank)

Filters and source access rules are part of every SQL query (`allowed_items`), so excluded
knowledge is never retrieved in the first place.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import Select, Text, cast, exists, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiError
from app.models import (
    CommunicationSource,
    ConversationThread,
    Equipment,
    Incident,
    KnowledgeCandidate,
    KnowledgeChunk,
    KnowledgeItem,
    knowledge_item_equipment,
    knowledge_item_incidents,
)
from app.models.enums import ApprovalStatus, ResolutionStatus

logger = logging.getLogger(__name__)

RRF_K = 60
# When semantic search ran and did not support an item, a keyword-only match must share more
# than a single term with it (ts_rank_cd normalized: one short-document hit ~= 0.09).
KEYWORD_ONLY_MIN_SCORE = 0.15
WEIGHTS = {"semantic": 1.0, "keyword": 1.0, "identifier": 2.0}  # exact IDs are operationally critical
# Inlined as a literal: PostgreSQL needs a regconfig constant, and the expression must
# match the GIN index from migration 0002 exactly to be used.
FTS_CONFIG = literal_column("'english'::regconfig")


def chunk_tsvector():
    return func.to_tsvector(FTS_CONFIG, KnowledgeChunk.content)

# Tokens that look like operational identifiers: letters followed by digits, optionally with
# more segments, e.g. INC-1042, PE-03, S42-RTR-01, OLT-17, "Site 42", ERR_503.
_IDENTIFIER = re.compile(r"\b[A-Za-z]{1,12}[-_ ]?\d+(?:[-_][A-Za-z0-9]+)*\b")


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def extract_identifiers(query: str) -> list[str]:
    seen: list[str] = []
    for match in _IDENTIFIER.finditer(query):
        token = normalize_identifier(match.group())
        if len(token) >= 3 and token not in seen:
            seen.append(token)
    return seen


def _sql_normalized(column):
    return func.regexp_replace(func.lower(column), "[^a-z0-9]", "", "g")


@dataclass
class SearchFilters:
    equipment_identifier: str | None = None
    incident_number: str | None = None
    approval_status: ApprovalStatus | None = None
    resolution_status: ResolutionStatus | None = None


@dataclass
class Signal:
    rank: int
    score: float


@dataclass
class RankedItem:
    item_id: uuid.UUID
    score: float = 0.0
    semantic: Signal | None = None  # score = cosine similarity
    keyword: Signal | None = None  # score = ts_rank_cd (normalized 0..1)
    identifier: Signal | None = None  # score = number of matched identifiers
    matched_identifiers: list[str] = field(default_factory=list)


@dataclass
class SearchOutcome:
    ranked: list[RankedItem]
    semantic_status: Literal["used", "no_embeddings", "unavailable", "not_configured"]
    semantic_detail: str | None
    identifiers: list[str]


def allowed_items(filters: SearchFilters) -> Select:
    """Knowledge the caller may see, with filters applied (used inside every retriever)."""
    query = (
        select(KnowledgeItem.id)
        .outerjoin(KnowledgeCandidate, KnowledgeItem.candidate_id == KnowledgeCandidate.id)
        .outerjoin(ConversationThread, KnowledgeCandidate.thread_id == ConversationThread.id)
        .outerjoin(CommunicationSource, ConversationThread.communication_source_id == CommunicationSource.id)
        # Knowledge from disabled (no longer authorized) sources is not searchable.
        .where(or_(CommunicationSource.id.is_(None), CommunicationSource.enabled.is_(True)))
    )
    if filters.approval_status is not None:
        query = query.where(KnowledgeItem.approval_status == filters.approval_status)
    if filters.resolution_status is not None:
        query = query.where(KnowledgeItem.resolution_status == filters.resolution_status)
    if filters.equipment_identifier:
        token = normalize_identifier(filters.equipment_identifier)
        query = query.where(exists(
            select(1)
            .select_from(knowledge_item_equipment.join(Equipment))
            .where(
                knowledge_item_equipment.c.knowledge_item_id == KnowledgeItem.id,
                or_(_sql_normalized(Equipment.equipment_identifier) == token,
                    _sql_normalized(Equipment.site_identifier) == token),
            )
        ))
    if filters.incident_number:
        token = normalize_identifier(filters.incident_number)
        query = query.where(exists(
            select(1)
            .select_from(knowledge_item_incidents.join(Incident))
            .where(
                knowledge_item_incidents.c.knowledge_item_id == KnowledgeItem.id,
                _sql_normalized(Incident.incident_number) == token,
            )
        ))
    return query


async def semantic_candidates(
    session: AsyncSession,
    vector: list[float],
    allowed: Select,
    *,
    pool: int,
    min_similarity: float,
    margin: float = 1.0,
) -> list[tuple[uuid.UUID, float]]:
    """Nearest knowledge by cosine similarity. Keeps matches above `min_similarity` and
    within `margin` of the best match (absolute similarities are compressed, so weak
    'nearest' neighbours of an unrelated query would otherwise still show up)."""
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    rows = await session.execute(
        select(KnowledgeChunk.knowledge_item_id, distance.label("distance"))
        .where(KnowledgeChunk.embedding.is_not(None), KnowledgeChunk.knowledge_item_id.in_(allowed))
        .order_by(distance)
        .limit(pool * 3)  # several chunks may belong to one item
    )
    best: dict[uuid.UUID, float] = {}
    for item_id, dist in rows:
        similarity = 1.0 - float(dist)
        if similarity >= min_similarity and item_id not in best:
            best[item_id] = similarity
    if not best:
        return []
    top = max(best.values())
    return [(i, sim) for i, sim in best.items() if sim >= top - margin][:pool]


def keyword_text(query: str) -> str:
    """Bare numbers ("3", "300") match unrelated text; identifiers that contain numbers are
    handled by the identifier retriever instead."""
    return re.sub(r"\b\d+\b", " ", query)


def _or_tsquery(query: str):
    """plainto_tsquery ANDs every word; a natural-language problem description should match
    knowledge that shares *some* terms, so the AND operators are turned into OR."""
    plain = cast(func.plainto_tsquery(FTS_CONFIG, query), Text)
    return func.to_tsquery(FTS_CONFIG, func.replace(plain, "&", "|"))


async def keyword_candidates(
    session: AsyncSession, query: str, allowed: Select, *, pool: int
) -> list[tuple[uuid.UUID, float]]:
    vector = chunk_tsvector()
    tsquery = _or_tsquery(keyword_text(query))
    rank = func.max(func.ts_rank_cd(vector, tsquery, 32)).label("rank")  # 32: rank/(rank+1)
    rows = await session.execute(
        select(KnowledgeChunk.knowledge_item_id, rank)
        .where(vector.op("@@")(tsquery), KnowledgeChunk.knowledge_item_id.in_(allowed))
        .group_by(KnowledgeChunk.knowledge_item_id)
        .order_by(rank.desc(), KnowledgeChunk.knowledge_item_id)
        .limit(pool)
    )
    return [(item_id, float(score)) for item_id, score in rows]


async def identifier_candidates(
    session: AsyncSession, tokens: list[str], allowed: Select, *, pool: int
) -> list[tuple[uuid.UUID, list[str]]]:
    if not tokens:
        return []
    matches: dict[uuid.UUID, dict[str, int]] = {}

    def add(item_id: uuid.UUID, token: str, weight: int) -> None:
        bucket = matches.setdefault(item_id, {})
        bucket[token] = max(bucket.get(token, 0), weight)

    # Structured identifiers (linked equipment, sites, incidents): strongest signal.
    equipment_rows = await session.execute(
        select(knowledge_item_equipment.c.knowledge_item_id,
               _sql_normalized(Equipment.equipment_identifier), _sql_normalized(Equipment.site_identifier))
        .select_from(knowledge_item_equipment.join(Equipment))
        .where(knowledge_item_equipment.c.knowledge_item_id.in_(allowed),
               or_(_sql_normalized(Equipment.equipment_identifier).in_(tokens),
                   _sql_normalized(Equipment.site_identifier).in_(tokens)))
    )
    for item_id, ident, site in equipment_rows:
        for token in tokens:
            if token in (ident, site):
                add(item_id, token, 2)
    incident_rows = await session.execute(
        select(knowledge_item_incidents.c.knowledge_item_id, _sql_normalized(Incident.incident_number))
        .select_from(knowledge_item_incidents.join(Incident))
        .where(knowledge_item_incidents.c.knowledge_item_id.in_(allowed),
               _sql_normalized(Incident.incident_number).in_(tokens))
    )
    for item_id, number in incident_rows:
        add(item_id, number, 2)

    # Identifiers written in the knowledge text (error codes, service and site names).
    normalized_content = _sql_normalized(KnowledgeChunk.content)
    text_rows = await session.execute(
        select(KnowledgeChunk.knowledge_item_id, normalized_content)
        .where(KnowledgeChunk.knowledge_item_id.in_(allowed),
               or_(*[normalized_content.contains(token) for token in tokens]))
    )
    for item_id, content in text_rows:
        for token in tokens:
            if token in content:
                add(item_id, token, 1)

    ranked = sorted(matches.items(), key=lambda kv: (-sum(kv[1].values()), -len(kv[1]), str(kv[0])))
    return [(item_id, sorted(found)) for item_id, found in ranked[:pool]]


def _competition_ranks(scores: list[float]) -> list[int]:
    """Equal scores share a rank ("1, 1, 3"), so ties are not broken arbitrarily."""
    ranks: list[int] = []
    for index, score in enumerate(scores):
        ranks.append(ranks[-1] if index and score == scores[index - 1] else index + 1)
    return ranks


def fuse(
    semantic: list[tuple[uuid.UUID, float]],
    keyword: list[tuple[uuid.UUID, float]],
    identifier: list[tuple[uuid.UUID, list[str]]],
) -> list[RankedItem]:
    items: dict[uuid.UUID, RankedItem] = {}

    def get(item_id: uuid.UUID) -> RankedItem:
        return items.setdefault(item_id, RankedItem(item_id=item_id))

    for rank, (item_id, similarity) in enumerate(semantic, start=1):
        entry = get(item_id)
        entry.semantic = Signal(rank, similarity)
        entry.score += WEIGHTS["semantic"] / (RRF_K + rank)
    keyword_ranks = _competition_ranks([score for _, score in keyword])
    for rank, (item_id, score) in zip(keyword_ranks, keyword, strict=True):
        entry = get(item_id)
        entry.keyword = Signal(rank, score)
        entry.score += WEIGHTS["keyword"] / (RRF_K + rank)
    for rank, (item_id, found) in enumerate(identifier, start=1):
        entry = get(item_id)
        entry.identifier = Signal(rank, float(len(found)))
        entry.matched_identifiers = found
        entry.score += WEIGHTS["identifier"] / (RRF_K + rank)
    def order(r: RankedItem) -> tuple:
        # Fusion score first; remaining ties go to the closer meaning, then a stable ID.
        return (-r.score, -(r.semantic.score if r.semantic else -1.0), str(r.item_id))

    return sorted(items.values(), key=order)


async def hybrid_search(
    session: AsyncSession,
    query: str,
    embedder: EmbeddingService | None,
    *,
    limit: int,
    filters: SearchFilters,
    pool: int = 20,
    min_similarity: float = 0.65,
    similarity_margin: float = 0.06,
) -> SearchOutcome:
    allowed = allowed_items(filters)
    tokens = extract_identifiers(query)

    semantic: list[tuple[uuid.UUID, float]] = []
    status: Literal["used", "no_embeddings", "unavailable", "not_configured"]
    detail: str | None = None
    has_embeddings = bool(await session.scalar(
        select(exists().where(KnowledgeChunk.embedding.is_not(None)))
    ))
    if embedder is None or not embedder.configured:
        status, detail = "not_configured", "Gemini is not configured; showing keyword matches only."
    elif not has_embeddings:
        status, detail = "no_embeddings", "No knowledge has been embedded yet; showing keyword matches only."
    else:
        try:
            vector = await embedder.embed_query(query)
            semantic = await semantic_candidates(
                session, vector, allowed, pool=pool, min_similarity=min_similarity, margin=similarity_margin
            )
            status = "used"
        except GeminiError as exc:
            # Keyword and identifier search still run; the response says semantic did not.
            logger.warning("Query embedding failed: %s", type(exc).__name__)
            status, detail = "unavailable", f"Semantic search unavailable: {exc}"

    keyword = await keyword_candidates(session, query, allowed, pool=pool)
    identifier = await identifier_candidates(session, tokens, allowed, pool=pool)
    ranked = fuse(semantic, keyword, identifier)
    if status == "used":
        ranked = [
            r for r in ranked
            if r.semantic or r.identifier or (r.keyword and r.keyword.score >= KEYWORD_ONLY_MIN_SCORE)
        ]
    ranked = ranked[:limit]
    return SearchOutcome(ranked=ranked, semantic_status=status, semantic_detail=detail, identifiers=tokens)
