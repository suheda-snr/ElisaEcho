"""Consolidate existing knowledge: find related items, store relationships, build groups.

    docker compose exec backend python -m app.scripts.consolidate_knowledge [--limit N] [--force] [--dry-run]

- Processes items never consolidated, marked for retry (e.g. Gemini was unavailable), or
  changed since their last consolidation. Unchanged pairs are not re-sent to Gemini.
- At most --limit items per run (default 20); each item compares with a bounded number of
  candidates (CONSOLIDATION_CANDIDATE_LIMIT), never all pairs. Re-run to continue.
- --force re-compares every item and regenerates group summaries.
- --dry-run only lists what would be processed (no Gemini calls, no writes).
- Removes group memberships of knowledge from disabled sources or rejected by an expert.
  Never deletes knowledge items or source messages. Safe to run repeatedly.
- CLI only: the API has no admin authentication, so there is no HTTP endpoint for this.
"""

import argparse
import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.ai.gemini import GeminiClient
from app.core.config import get_settings
from app.db.session import DatabaseNotConfiguredError, dispose_engine, get_sessionmaker
from app.db.url import InvalidDatabaseUrlError
from app.services.consolidation.service import (
    ConsolidationConfig,
    consolidate_item,
    items_needing_consolidation,
    remove_ineligible_memberships,
)


async def run(limit: int, force: bool, dry_run: bool) -> int:
    settings = get_settings()
    gemini = GeminiClient.from_settings(settings)
    config = ConsolidationConfig.from_settings(settings)
    try:
        async with get_sessionmaker()() as session:
            todo = await items_needing_consolidation(session, force=force)
        print(f"Items to consolidate: {len(todo)} (processing at most {limit})")
        if dry_run:
            for item_id in todo[:limit]:
                print(f"  would consolidate {item_id}")
            return 0
        async with get_sessionmaker()() as session:
            removed = await remove_ineligible_memberships(session)
        if removed:
            print(f"Removed {removed} membership(s) of ineligible knowledge.")
        if not todo:
            print("Everything is consolidated.")
            return 0
        if not gemini.configured:
            print("GEMINI_API_KEY is not set; cannot compare knowledge.", file=sys.stderr)
            return 1

        failures = 0
        for item_id in todo[:limit]:
            async with get_sessionmaker()() as session:
                outcome = await consolidate_item(session, item_id, gemini, config, force=force)
            group = f", group {outcome.group_action}" if outcome.group_action else ""
            print(f"  {item_id}: {outcome.status} ({outcome.compared} compared, {outcome.reused} reused, "
                  f"{outcome.related} related{group})")
            if outcome.status == "retry":
                failures += 1
                print(f"    retry later: {outcome.error}", file=sys.stderr)
                if outcome.error and "Embedding pending" not in outcome.error:
                    print("Stopped at the first Gemini failure; re-run later.", file=sys.stderr)
                    return 1
        print(f"Done ({failures} item(s) need a retry)." if failures else "Done.")
        return 0
    except (DatabaseNotConfiguredError, InvalidDatabaseUrlError) as exc:
        print(f"Consolidation aborted: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(f"Consolidation stopped: database error ({type(exc).__name__}). Re-run to continue.",
              file=sys.stderr)
        return 1
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=20, help="max items to process this run (default 20)")
    parser.add_argument("--force", action="store_true", help="re-compare everything and regenerate summaries")
    parser.add_argument("--dry-run", action="store_true", help="only report what would be processed")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    sys.exit(asyncio.run(run(args.limit, args.force, args.dry_run)))


if __name__ == "__main__":
    main()
