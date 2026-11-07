"""Email as a knowledge source: parse messages, group them into threads, store them.

No extra work for specialists: experts keep answering by email and CC (or forward to) a shared
knowledge mailbox. Each mailbox is a communication source; its `enabled` flag is the
allowlist. Emails then go through exactly the same discovery pipeline as chat threads.

- Parsing: RFC 822 (.eml) or a simple JSON shape. Plain text preferred; HTML is reduced to text.
- Cleaning: quoted replies ("> ...", "On ... wrote:", "-----Original Message-----") and
  signatures ("-- ") are removed, so each stored message contains only what its author wrote.
- Threading: References / In-Reply-To first (a reply joins the thread of the message it
  answers), then the normalized subject ("RE: X" joins "X") within the same mailbox.
- Idempotent: the Message-ID is the external message id; re-importing changes nothing.
"""

import email
import email.policy
import hashlib
import html
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommunicationSource, ConversationThread, Message
from app.models.enums import SourceType
from app.schemas.threads import MessageIngest, ThreadIngest
from app.services.ingestion import upsert_messages, upsert_source, upsert_thread

MAX_BODY = 20_000
_PREFIX = re.compile(r"^\s*((re|fw|fwd|aw|vs|sv|vl)\s*(\[\d+\])?\s*:\s*)+", re.I)
_QUOTE_HEADERS = (
    re.compile(r"^\s*On .{3,200}wrote:\s*$", re.I),  # Gmail/Apple style
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.I),  # Outlook
    re.compile(r"^\s*From:\s.+$"),  # Outlook reply header block ("From: ... Sent: ...")
    re.compile(r"^\s*_{10,}\s*$"),  # Outlook separator line
)


class EmailParseError(ValueError):
    pass


@dataclass
class ParsedEmail:
    message_id: str
    subject: str
    from_name: str | None
    from_address: str
    sent_at: datetime
    body: str
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    to: list[str] = field(default_factory=list)


def normalize_subject(subject: str) -> str:
    return " ".join(_PREFIX.sub("", subject or "").split()).lower()


def clean_subject(subject: str) -> str:
    return " ".join(_PREFIX.sub("", subject or "").split()) or "(no subject)"


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", value)
    return html.unescape(re.sub(r"<[^>]+>", " ", value))


def clean_body(text: str) -> str:
    """Keep only what the author wrote: drop quoted history and the signature."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: list[str] = []
    for line in lines:
        if line.rstrip() == "--" or line == "-- ":
            break  # signature delimiter
        if any(p.match(line) for p in _QUOTE_HEADERS) and kept:
            break  # everything below is the quoted earlier message
        if line.lstrip().startswith(">"):
            continue
        kept.append(line.rstrip())
    body = "\n".join(kept).strip()
    return re.sub(r"\n{3,}", "\n\n", body)[:MAX_BODY]


def _ids(value: str | None) -> list[str]:
    return re.findall(r"<[^<>\s]+>", value or "")


def _fallback_id(sender: str, sent_at: datetime, body: str) -> str:
    digest = hashlib.sha256(f"{sender}|{sent_at.isoformat()}|{body}".encode()).hexdigest()[:24]
    return f"<generated-{digest}@elisa-echo.invalid>"


def parse_eml(raw: str | bytes) -> ParsedEmail:
    data = raw.encode() if isinstance(raw, str) else raw
    msg = email.message_from_bytes(data, policy=email.policy.default)
    if not msg.get("From"):
        raise EmailParseError("Not an email: missing From header.")
    name, address = parseaddr(str(msg.get("From")))
    try:
        sent_at = parsedate_to_datetime(str(msg.get("Date"))) if msg.get("Date") else datetime.now(UTC)
    except (TypeError, ValueError):
        sent_at = datetime.now(UTC)
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)
    part = msg.get_body(preferencelist=("plain", "html"))
    content = part.get_content() if part is not None else ""
    if part is not None and part.get_content_type() == "text/html":
        content = _html_to_text(content)
    body = clean_body(content)
    message_id = (_ids(str(msg.get("Message-ID") or "")) or [None])[0] or _fallback_id(address, sent_at, body)
    return ParsedEmail(
        message_id=message_id[:255], subject=str(msg.get("Subject") or ""), from_name=name or None,
        from_address=address.lower() or "unknown", sent_at=sent_at, body=body,
        in_reply_to=(_ids(str(msg.get("In-Reply-To") or "")) or [None])[0],
        references=_ids(str(msg.get("References") or "")),
        to=[a.lower() for _, a in getaddresses([str(msg.get("To") or ""), str(msg.get("Cc") or "")]) if a],
    )


def parse_json(obj: dict[str, Any]) -> ParsedEmail:
    """{"from": "Name <a@b>", "subject", "date" (ISO), "body", "message_id"?, "in_reply_to"?, "references"?}"""
    if not obj.get("from") or not obj.get("body"):
        raise EmailParseError("JSON email needs at least 'from' and 'body'.")
    name, address = parseaddr(str(obj["from"]))
    try:
        sent_at = datetime.fromisoformat(str(obj["date"])) if obj.get("date") else datetime.now(UTC)
    except ValueError as exc:
        raise EmailParseError(f"Invalid date: {obj.get('date')!r}") from exc
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)
    body = clean_body(str(obj["body"]))
    refs = obj.get("references") or []
    return ParsedEmail(
        message_id=str(obj.get("message_id") or _fallback_id(address, sent_at, body))[:255],
        subject=str(obj.get("subject") or ""), from_name=name or None, from_address=address.lower() or "unknown",
        sent_at=sent_at, body=body, in_reply_to=obj.get("in_reply_to"),
        references=refs if isinstance(refs, list) else _ids(str(refs)),
    )


@dataclass
class EmailImportResult:
    source_id: uuid.UUID | None
    threads: list[tuple[uuid.UUID, str]]  # (thread id, title) that received new messages
    imported: int
    duplicates: int
    skipped_reason: str | None = None


async def _thread_for(session: AsyncSession, source_id: uuid.UUID, mail: ParsedEmail) -> tuple[str, str]:
    """(external thread id, title) for an email."""
    for ref in [*reversed(mail.references), mail.in_reply_to]:
        if not ref:
            continue
        external = await session.scalar(
            select(ConversationThread.external_thread_id)
            .join(Message, Message.thread_id == ConversationThread.id)
            .where(ConversationThread.communication_source_id == source_id, Message.external_message_id == ref)
        )
        if external:
            return external, clean_subject(mail.subject)
    subject = normalize_subject(mail.subject)
    if subject:
        return f"subject:{hashlib.sha256(subject.encode()).hexdigest()[:32]}", clean_subject(mail.subject)
    root = (mail.references or [mail.in_reply_to or mail.message_id])[0]
    return f"message:{root}"[:255], clean_subject(mail.subject)


async def import_emails(session: AsyncSession, mailbox: str, mails: list[ParsedEmail], *,
                        source_name: str | None = None) -> EmailImportResult:
    """Store emails in the mailbox's source (created on first use). Disabled mailboxes are not
    imported. Caller commits."""
    mailbox = mailbox.strip().lower()
    external = f"mailbox:{mailbox}"
    existing = await session.scalar(select(CommunicationSource).where(
        CommunicationSource.source_type == SourceType.EMAIL, CommunicationSource.external_source_id == external))
    if existing is not None and not existing.enabled:
        return EmailImportResult(existing.id, [], 0, 0, "Mailbox is disabled; emails were not imported.")
    source_id = await upsert_source(session, name=source_name or f"Email: {mailbox}",
                                    source_type=SourceType.EMAIL, external_source_id=external)

    touched: dict[uuid.UUID, str] = {}
    imported = duplicates = 0
    for mail in sorted(mails, key=lambda m: m.sent_at):
        if not mail.body:
            continue
        thread_external, title = await _thread_for(session, source_id, mail)
        thread_id = await upsert_thread(session, source_id, ThreadIngest(external_thread_id=thread_external,
                                                                          title=title[:500]))
        known = await session.scalar(select(Message.id).where(
            Message.thread_id == thread_id, Message.external_message_id == mail.message_id))
        if known is not None:
            duplicates += 1
            continue
        await upsert_messages(session, thread_id, [MessageIngest(
            external_message_id=mail.message_id, author_external_id=mail.from_address,
            author_display_name=mail.from_name, content=mail.body, sent_at=mail.sent_at,
            source_url=f"mid:{mail.message_id.strip('<>')}",
        )])
        await session.flush()
        touched[thread_id] = title
        imported += 1
    return EmailImportResult(source_id, list(touched.items()), imported, duplicates)
