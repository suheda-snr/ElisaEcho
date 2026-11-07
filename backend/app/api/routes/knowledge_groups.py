"""Knowledge groups: AI-suggested clusters of related cases (read-only).

Groups are derived by the consolidation pipeline; there are no write endpoints because the
API has no admin authentication. Rebuilding/backfilling is a CLI command
(`python -m app.scripts.consolidate_knowledge`). Only knowledge from enabled sources that an
expert has not rejected is shown; there is no per-user authorization yet.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, PaginationDep
from app.schemas.common import Page
from app.schemas.consolidation import GroupBrief, GroupDetail, RelationshipRead
from app.services.consolidation import queries

router = APIRouter(prefix="/knowledge-groups", tags=["knowledge groups"])

NOT_FOUND = {404: {"description": "Group not found or not visible"}}


@router.get("", response_model=Page[GroupBrief], summary="List knowledge groups")
async def list_groups(session: DbSession, page: PaginationDep) -> Page[GroupBrief]:
    items, total = await queries.list_groups(session, limit=page.limit, offset=page.offset)
    return Page[GroupBrief](items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{group_id}", response_model=GroupDetail, summary="Group summary and member cases",
            responses=NOT_FOUND)
async def get_group(group_id: uuid.UUID, session: DbSession) -> GroupDetail:
    group = await queries.get_group(session, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge group not found.")
    return group


@router.get("/{group_id}/relationships", response_model=list[RelationshipRead],
            summary="Pairwise relationships between the group's cases", responses=NOT_FOUND)
async def get_group_relationships(group_id: uuid.UUID, session: DbSession) -> list[RelationshipRead]:
    rows = await queries.group_relationships(session, group_id)
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge group not found.")
    return rows
