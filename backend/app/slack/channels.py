"""Channel allowlist, stored as one communication source per Slack channel.

`communication_sources.enabled` decides whether a channel is monitored. Disabling a channel
stops ingestion; already stored messages and knowledge are kept.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommunicationSource
from app.models.enums import SourceType
from app.services.ingestion import upsert_source
from app.slack.events import source_external_id


async def set_channel_monitoring(
    session: AsyncSession, team_id: str, channel_id: str, name: str, *, enabled: bool
) -> CommunicationSource:
    """Create or update the channel's source with the given monitoring flag. Caller commits."""
    source_id = await upsert_source(session, name=name, source_type=SourceType.SLACK,
                                    external_source_id=source_external_id(team_id, channel_id))
    await session.execute(
        update(CommunicationSource).where(CommunicationSource.id == source_id).values(enabled=enabled)
    )
    source = await session.get(CommunicationSource, source_id, populate_existing=True)
    assert source is not None
    return source


async def slack_sources(session: AsyncSession) -> list[CommunicationSource]:
    return list(await session.scalars(
        select(CommunicationSource)
        .where(CommunicationSource.source_type == SourceType.SLACK)
        .order_by(CommunicationSource.name)
    ))


def channel_id_of(source: CommunicationSource) -> str:
    return source.external_source_id.split(":", 1)[1]
