"""Persisted connector state and operational events (shared by worker and API)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntegrationEvent, IntegrationState

SLACK = "slack"


async def update_state(session: AsyncSession, name: str, **fields: Any) -> None:
    """Upsert the connector state row; only the given fields change. Caller commits."""
    now = datetime.now(UTC)
    changed = {**fields, "updated_at": now}
    # A brand-new row needs a status; existing rows keep theirs unless one is given.
    stmt = insert(IntegrationState).values({"name": name, "status": "unknown", **changed})
    stmt = stmt.on_conflict_do_update(
        index_elements=["name"],
        set_={key: stmt.excluded[key] for key in changed},
    )
    await session.execute(stmt)


async def get_state(session: AsyncSession, name: str) -> IntegrationState | None:
    return await session.scalar(
        select(IntegrationState).where(IntegrationState.name == name).execution_options(populate_existing=True)
    )


async def log_event(
    session: AsyncSession,
    name: str,
    kind: str,
    message: str,
    *,
    level: str = "info",
    channel_id: str | None = None,
    thread_id: uuid.UUID | None = None,
) -> None:
    """Record an operational event (never message content or secrets). Caller commits."""
    session.add(IntegrationEvent(integration=name, kind=kind, level=level, message=message[:500],
                                 channel_id=channel_id, thread_id=thread_id))


async def recent_events(session: AsyncSession, name: str, limit: int = 50) -> list[IntegrationEvent]:
    rows = await session.scalars(
        select(IntegrationEvent)
        .where(IntegrationEvent.integration == name)
        .order_by(IntegrationEvent.created_at.desc())
        .limit(limit)
    )
    return list(rows)
