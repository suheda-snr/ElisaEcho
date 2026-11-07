"""Import emails (.eml or .json files, or folders of them) into a mailbox knowledge source.

    docker compose exec backend python -m app.scripts.import_email app/seed/emails [--mailbox X] [--analyze]

- Idempotent: the Message-ID is the key; re-importing the same email changes nothing.
- Threads replies with their original (References/In-Reply-To, then subject).
- Quoted history and signatures are removed before storing.
- --analyze runs discovery (Gemini) for the email threads that received new messages;
  without it the threads are left pending for the running backend or a later analysis.
- Never deletes anything. A disabled mailbox source is not imported.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.ai.embeddings import EmbeddingService
from app.ai.gemini import GeminiClient
from app.core.config import get_settings
from app.db.session import dispose_engine, get_sessionmaker
from app.seed.demo_data import DEMO_MAILBOX
from app.services.discovery.factory import build_discovery_engine
from app.services.email_ingest import EmailParseError, import_emails, parse_eml, parse_json


def _files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        out += sorted([*p.glob("*.eml"), *p.glob("*.json")]) if p.is_dir() else [p]
    return out


def _parse(path: Path):
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return [parse_json(d) for d in (data if isinstance(data, list) else [data])]
    return [parse_eml(path.read_bytes())]


async def run(paths: list[str], mailbox: str, analyze: bool) -> int:
    mails = []
    for path in _files(paths):
        try:
            mails += _parse(path)
        except (OSError, EmailParseError, ValueError) as exc:
            print(f"Skipped {path}: {exc}", file=sys.stderr)
    if not mails:
        print("No emails found.", file=sys.stderr)
        return 1
    try:
        async with get_sessionmaker()() as session:
            result = await import_emails(session, mailbox, mails)
            await session.commit()
        print(f"Mailbox {mailbox}: {result.imported} imported, {result.duplicates} already known"
              + (f" ({result.skipped_reason})" if result.skipped_reason else ""))
        for _, title in result.threads:
            print(f"  thread: {title}")
        if analyze and result.threads:
            settings = get_settings()
            gemini = GeminiClient.from_settings(settings)
            engine = build_discovery_engine(settings, gemini, EmbeddingService.from_settings(settings, gemini))
            for thread_id, title in result.threads:
                outcome = await engine.run_analysis(thread_id)
                print(f"  analyzed {title!r}: {outcome.status} {outcome.resolution_status or ''} {outcome.error or ''}")
            await engine.drain_consolidation()
        return 0
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help=".eml/.json files or folders")
    parser.add_argument("--mailbox", default=DEMO_MAILBOX, help=f"mailbox source (default {DEMO_MAILBOX})")
    parser.add_argument("--analyze", action="store_true", help="analyze the imported threads now (Gemini)")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.paths, args.mailbox, args.analyze)))


if __name__ == "__main__":
    main()
