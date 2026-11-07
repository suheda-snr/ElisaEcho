"""Synthetic demo emails (Elisa Appendix A3 and an older site-access email), as .eml files.

They are imported through the real email pipeline (parsing, quote stripping, threading) into
the synthetic demo mailbox, exactly as a forwarded/CC'd email would be.
"""

from pathlib import Path

from app.services.email_ingest import ParsedEmail, parse_eml

EMAIL_DIR = Path(__file__).parent / "emails"


def demo_email_files() -> list[Path]:
    return sorted(EMAIL_DIR.glob("*.eml"))


def load_demo_emails() -> list[ParsedEmail]:
    return [parse_eml(path.read_bytes()) for path in demo_email_files()]
