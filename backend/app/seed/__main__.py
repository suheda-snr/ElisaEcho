"""CLI: `python -m app.seed` (inside the backend container).

Requires ENVIRONMENT=development or test. Safe to run repeatedly.
"""

import asyncio
import sys

from app.core.config import get_settings
from app.db.session import DatabaseNotConfiguredError, dispose_engine, get_sessionmaker
from app.db.url import InvalidDatabaseUrlError
from app.seed.seed import SeedNotAllowedError, ensure_seed_allowed, seed_demo_data


async def main() -> int:
    settings = get_settings()
    try:
        ensure_seed_allowed(settings)
        async with get_sessionmaker()() as session:
            summary = await seed_demo_data(session, settings)
            await session.commit()
    except (SeedNotAllowedError, DatabaseNotConfiguredError, InvalidDatabaseUrlError) as exc:
        print(f"Seed aborted: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - report without leaking connection details
        print(f"Seed failed: {type(exc).__name__}. Is the database reachable and migrated?", file=sys.stderr)
        return 1
    finally:
        await dispose_engine()

    print(
        f"Seeded {summary.threads} synthetic threads with {summary.messages} messages "
        "(idempotent: existing rows were updated, nothing was deleted)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
