"""Load the synthetic demo conversations into the database.

Safety rules:
- Runs only when ENVIRONMENT is `development` or `test`.
- Additive and idempotent: upserts keyed on external IDs, so running it again
  changes nothing. It never deletes or truncates anything.
- Touches only its own synthetic source, threads and messages.
- Stores raw messages only; no knowledge is pre-extracted.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DEVELOPMENT_ENVIRONMENTS, Settings
from app.schemas.threads import MessageIngest, ThreadIngest
from app.seed.demo_data import (
    DEMO_SOURCE_EXTERNAL_ID,
    DEMO_SOURCE_NAME,
    DEMO_SOURCE_TYPE,
    DEMO_THREADS,
    demo_message_url,
)
from app.services.ingestion import upsert_messages, upsert_source, upsert_thread


class SeedNotAllowedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedSummary:
    threads: int
    messages: int


def ensure_seed_allowed(settings: Settings) -> None:
    if not settings.is_development:
        allowed = ", ".join(sorted(DEVELOPMENT_ENVIRONMENTS))
        raise SeedNotAllowedError(
            f"Refusing to seed demo data: ENVIRONMENT is '{settings.environment}'. "
            f"Seeding is only allowed when ENVIRONMENT is one of: {allowed}."
        )


async def seed_demo_data(session: AsyncSession, settings: Settings) -> SeedSummary:
    """Upsert the demo conversations. The caller is responsible for committing."""
    ensure_seed_allowed(settings)

    source_id = await upsert_source(
        session,
        name=DEMO_SOURCE_NAME,
        source_type=DEMO_SOURCE_TYPE,
        external_source_id=DEMO_SOURCE_EXTERNAL_ID,
    )

    message_count = 0
    for demo in DEMO_THREADS:
        thread_id = await upsert_thread(
            session, source_id, ThreadIngest(external_thread_id=demo.external_id, title=demo.title)
        )
        messages = [
            MessageIngest(
                external_message_id=m.external_id,
                author_external_id=m.author_id,
                author_display_name=m.author_name,
                content=m.content,
                sent_at=m.sent_at,
                source_url=demo_message_url(demo.external_id, m.external_id),
            )
            for m in demo.messages
        ]
        await upsert_messages(session, thread_id, messages)
        message_count += len(messages)

    return SeedSummary(threads=len(DEMO_THREADS), messages=message_count)
