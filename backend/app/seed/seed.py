"""Load the synthetic demo conversations into the database.

Safety rules:
- Runs only when ENVIRONMENT is `development` or `test`.
- Additive and idempotent: upserts keyed on external IDs, so running it again
  changes nothing. It never deletes or truncates anything.
- Touches only its own synthetic source, threads and messages.
- Stores raw messages only; no knowledge is pre-extracted.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DEVELOPMENT_ENVIRONMENTS, Settings
from app.models import ConversationThread
from app.schemas.threads import MessageIngest, ThreadIngest
from app.seed.demo_data import DEMO_MAILBOX, DEMO_SOURCES, DEMO_THREADS, demo_message_url
from app.seed.demo_emails import load_demo_emails
from app.seed.inventory import ensure_inventory
from app.services.email_ingest import import_emails
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

    await ensure_inventory(session)
    source_ids = {}
    for key, (name, source_type, external_id) in DEMO_SOURCES.items():
        if key != "email":
            source_ids[key] = await upsert_source(
                session, name=name, source_type=source_type, external_source_id=external_id)

    message_count = 0
    for demo in DEMO_THREADS:
        source_id = source_ids[demo.source]
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

    emails = await import_emails(session, DEMO_MAILBOX, load_demo_emails(),
                                 source_name=DEMO_SOURCES["email"][0])
    message_count += emails.imported + emails.duplicates
    email_threads = int(await session.scalar(select(func.count()).select_from(ConversationThread).where(
        ConversationThread.communication_source_id == emails.source_id)) or 0)
    return SeedSummary(threads=len(DEMO_THREADS) + email_threads, messages=message_count)
