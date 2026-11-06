from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommunicationSource
from app.schemas.sources import SourceCreate


class SourceAlreadyExistsError(Exception):
    """A source with the same type and external ID already exists."""


async def list_sources(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[CommunicationSource], int]:
    total = await session.scalar(select(func.count()).select_from(CommunicationSource)) or 0
    result = await session.scalars(
        select(CommunicationSource)
        .order_by(CommunicationSource.created_at, CommunicationSource.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result), total


async def create_source(session: AsyncSession, data: SourceCreate) -> CommunicationSource:
    source = CommunicationSource(**data.model_dump())
    session.add(source)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise SourceAlreadyExistsError from exc
    await session.refresh(source)
    return source
