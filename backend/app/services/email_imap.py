"""Read a real mailbox folder over IMAP and feed new emails into the email pipeline.

Safety:
- Read-only: the folder is SELECTed with readonly=True and bodies are fetched with
  BODY.PEEK[], so nothing is deleted, moved or marked as read.
- Bounded: only one folder/label, only emails from the last `since_days` days on the first
  check, then only emails newer than the last one read (IMAP UID), at most `max_per_poll`
  per check. Every email costs one Gemini analysis, so a dedicated label is recommended.
- The password is decrypted only in memory for the IMAP login; it is never logged or returned.
  Email content is not logged either.
"""

import asyncio
import imaplib
import logging
import re
import socket
import ssl
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailConnection
from app.services.credentials import CredentialsError, decrypt
from app.services.email_ingest import EmailParseError, import_emails, parse_eml

logger = logging.getLogger(__name__)

IMAP_TIMEOUT_SECONDS = 30
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class ImapError(Exception):
    """A problem safe to show in the UI (never contains the password)."""


@dataclass(frozen=True)
class ImapAccount:
    host: str
    port: int
    username: str
    password: str
    folder: str


@dataclass
class FetchResult:
    uid_validity: int
    message_count: int
    messages: list[tuple[int, bytes]] = field(default_factory=list)
    remaining: int = 0


def _quote(folder: str) -> str:
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_date(day: date) -> str:
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"  # locale-independent


def _folders(client: imaplib.IMAP4) -> list[str]:
    typ, data = client.list()
    names = []
    for line in data or []:
        text = line.decode(errors="replace") if isinstance(line, bytes) else str(line)
        match = re.search(r'"([^"]*)"\s*$', text) or re.search(r"(\S+)\s*$", text)
        if match and "\\Noselect" not in text:
            names.append(match.group(1))
    return names


def _open(account: ImapAccount) -> tuple[imaplib.IMAP4, int, int]:
    """Connect, log in and select the folder read-only. Returns (client, uid validity, count)."""
    try:
        client = imaplib.IMAP4_SSL(account.host, account.port, timeout=IMAP_TIMEOUT_SECONDS,
                                   ssl_context=ssl.create_default_context())
    except (OSError, socket.timeout, ssl.SSLError) as exc:
        raise ImapError(f"Could not reach {account.host}:{account.port} ({type(exc).__name__}).") from None
    try:
        client.login(account.username, account.password)
    except imaplib.IMAP4.error:
        client.shutdown()
        raise ImapError("Login failed. Check the email address and the app password (Gmail needs "
                        "2-Step Verification and an app password, not your normal password).") from None
    typ, data = client.select(_quote(account.folder), readonly=True)
    if typ != "OK":
        available = ", ".join(_folders(client)[:15])
        client.logout()
        raise ImapError(f"Folder or label {account.folder!r} not found. Available: {available}")
    count = int(data[0] or 0) if data and data[0] else 0
    typ, values = client.response("UIDVALIDITY")
    validity = int(values[0]) if values and values[0] else 0
    return client, validity, count


def check_account(account: ImapAccount) -> int:
    """Log in and open the folder; returns the number of emails in it."""
    client, _, count = _open(account)
    client.logout()
    return count


def fetch_new(account: ImapAccount, *, uid_validity: int | None, last_uid: int | None, since: date,
              limit: int) -> FetchResult:
    client, validity, count = _open(account)
    try:
        if uid_validity is not None and uid_validity != validity:
            last_uid = None  # the folder was recreated: UIDs changed, start again from `since`
        if last_uid:
            typ, data = client.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        else:
            typ, data = client.uid("SEARCH", None, "SINCE", _imap_date(since))
        if typ != "OK":
            raise ImapError("The mail server rejected the search.")
        uids = sorted(int(u) for u in (data[0] or b"").split() if not last_uid or int(u) > last_uid)
        batch = uids[:limit]
        messages = []
        for uid in batch:
            typ, parts = client.uid("FETCH", str(uid), "(BODY.PEEK[])")  # PEEK: stays unread
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple) and len(p) == 2), None)
            if typ == "OK" and raw:
                messages.append((uid, raw))
        return FetchResult(validity, count, messages, remaining=len(uids) - len(batch))
    finally:
        try:
            client.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def account_of(connection: EmailConnection) -> ImapAccount:
    try:
        password = decrypt(connection.password_encrypted)
    except CredentialsError as exc:
        raise ImapError(str(exc)) from None
    return ImapAccount(connection.host, connection.port, connection.username, password, connection.folder)


@dataclass
class PollOutcome:
    connection_id: uuid.UUID
    status: str  # connected | error | disabled | missing
    fetched: int = 0
    imported: int = 0
    duplicates: int = 0
    remaining: int = 0
    threads: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    error: str | None = None


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def poll_connection(session_factory: SessionFactory, connection_id: uuid.UUID,
                          fetch=fetch_new) -> PollOutcome:
    async with session_factory() as session:
        conn = await session.get(EmailConnection, connection_id)
        if conn is None:
            return PollOutcome(connection_id, "missing")
        if not conn.enabled:
            return PollOutcome(connection_id, "disabled")
        now = datetime.now(UTC)
        try:
            account = account_of(conn)
            result = await asyncio.to_thread(
                fetch, account, uid_validity=conn.uid_validity, last_uid=conn.last_uid,
                since=(now - timedelta(days=conn.since_days)).date(), limit=conn.max_per_poll)
        except ImapError as exc:
            conn.status, conn.last_error, conn.last_checked_at = "error", str(exc), now
            await session.commit()
            return PollOutcome(connection_id, "error", error=str(exc))

        mails = []
        for uid, raw in result.messages:
            try:
                mails.append(parse_eml(raw))
            except (EmailParseError, ValueError, LookupError):
                logger.warning("Skipped an unparseable email (uid %s) in connection %s", uid, connection_id)
        imported = await import_emails(session, conn.username, mails,
                                       source_name=f"Email: {conn.username} ({conn.folder})")
        conn.uid_validity = result.uid_validity
        if result.messages:
            conn.last_uid = max(uid for uid, _ in result.messages)
        elif conn.last_uid is None:
            conn.last_uid = 0  # nothing in the window: from now on only newer emails
        conn.imported_count += imported.imported
        conn.folder_message_count = result.message_count
        conn.source_id = imported.source_id
        conn.status, conn.last_error, conn.last_checked_at = "connected", imported.skipped_reason, now
        await session.commit()
        return PollOutcome(connection_id, "connected", fetched=len(result.messages), imported=imported.imported,
                           duplicates=imported.duplicates, remaining=result.remaining, threads=imported.threads)


class EmailPoller:
    """Checks every enabled mailbox connection periodically (inside the API process) and hands
    new email threads to the discovery engine."""

    def __init__(self, session_factory: SessionFactory, schedule: Callable[[uuid.UUID, str], None],
                 interval_seconds: float = 60.0) -> None:
        self.session_factory = session_factory
        self.schedule = schedule
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._soon: set[asyncio.Task] = set()

    def check_soon(self, connection_id: uuid.UUID) -> None:
        """Run a check in the background (e.g. right after connecting)."""
        task = asyncio.create_task(self.poll_now(connection_id))
        self._soon.add(task)
        task.add_done_callback(self._soon.discard)

    async def drain(self) -> None:
        while self._soon:
            await asyncio.gather(*list(self._soon), return_exceptions=True)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def poll_now(self, connection_id: uuid.UUID) -> PollOutcome:
        async with self._lock:
            outcome = await poll_connection(self.session_factory, connection_id)
        for thread_id, title in outcome.threads:
            try:
                self.schedule(thread_id, title)
            except Exception:  # noqa: BLE001 - stored emails can be re-analyzed later
                logger.exception("Could not schedule analysis for an email thread")
        return outcome

    async def poll_all(self) -> None:
        try:
            async with self.session_factory() as session:
                ids = list(await session.scalars(select(EmailConnection.id).where(EmailConnection.enabled.is_(True))))
        except Exception:  # noqa: BLE001 - database down: try again next round
            logger.warning("Email poller could not list connections")
            return
        for connection_id in ids:
            try:
                await self.poll_now(connection_id)
            except Exception:  # noqa: BLE001
                logger.exception("Email poll failed for connection %s", connection_id)

    async def _loop(self) -> None:
        while True:
            await self.poll_all()
            await asyncio.sleep(self.interval)
