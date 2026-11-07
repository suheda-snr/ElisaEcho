"""Generate missing or outdated embeddings for stored knowledge.

    docker compose exec backend python -m app.scripts.backfill_embeddings [--limit N] [--force] [--dry-run]

- Syncs chunk text for every knowledge item (no API calls). Chunks whose text changed lose
  their old embedding; unchanged chunks keep theirs and are skipped.
- Embeds at most --limit pending chunks (default 100) per run, so it never processes an
  unbounded dataset. Re-run to continue.
- --force marks every chunk as outdated first (use after changing GEMINI_EMBEDDING_MODEL).
- Stops at the first Gemini failure (e.g. quota); everything not embedded stays pending.
- Never deletes knowledge items or source messages. Safe to run repeatedly.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiClient
from app.core.config import get_settings
from app.db.session import DatabaseNotConfiguredError, dispose_engine, get_sessionmaker
from app.db.url import InvalidDatabaseUrlError
from app.models import KnowledgeChunk, KnowledgeItem
from app.services.retrieval.indexing import embed_pending_chunks, embed_pending_count, sync_item_chunks


async def run(limit: int, force: bool, dry_run: bool) -> int:
    settings = get_settings()
    embedder = EmbeddingService.from_settings(settings, GeminiClient.from_settings(settings))
    try:
        async with get_sessionmaker()() as session:
            item_ids = list(await session.scalars(select(KnowledgeItem.id).order_by(KnowledgeItem.created_at)))
            print(f"Knowledge items: {len(item_ids)}")

            changed = 0
            for item_id in item_ids:
                changed += (await sync_item_chunks(session, item_id, commit=not dry_run)).changed
            verb = "would change" if dry_run else "synced"
            print(f"Chunk text {verb}: {changed} new or changed chunk(s)")

            if force and not dry_run:
                result = await session.execute(update(KnowledgeChunk).values(embedding=None))
                await session.commit()
                print(f"--force: marked {result.rowcount} chunk(s) for re-embedding")

            pending = await embed_pending_count(session)
            print(f"Pending embeddings: {pending} (model {embedder.model}, {embedder.dimension} dims)")
            if dry_run or pending == 0:
                print("Nothing embedded (dry run)." if dry_run else "All embeddings are up to date.")
                return 0
            if not embedder.configured:
                print("GEMINI_API_KEY is not set; cannot embed.", file=sys.stderr)
                return 1

            done = 0
            while done < limit:
                batch = await embed_pending_chunks(session, embedder, limit=min(10, limit - done))
                done += batch.embedded
                print(f"  embedded {done} so far, {batch.pending} pending")
                if batch.error:
                    print(f"Stopped: {batch.error} Remaining chunks stay pending; re-run later.",
                          file=sys.stderr)
                    return 1
                if batch.pending == 0 or batch.embedded == 0:
                    break
            print(f"Done: embedded {done} chunk(s).")
            return 0
    except (DatabaseNotConfiguredError, InvalidDatabaseUrlError) as exc:
        print(f"Backfill aborted: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Connection details are not printed; progress so far is committed and safe.
        print(f"Backfill stopped: database error ({type(exc).__name__}). Re-run to continue.",
              file=sys.stderr)
        return 1
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=100, help="max chunks to embed this run (default 100)")
    parser.add_argument("--force", action="store_true", help="re-embed everything (e.g. after a model change)")
    parser.add_argument("--dry-run", action="store_true", help="only report what would be embedded")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    sys.exit(asyncio.run(run(args.limit, args.force, args.dry_run)))


if __name__ == "__main__":
    main()
