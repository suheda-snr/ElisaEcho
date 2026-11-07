"""Email knowledge source: import emails (development only) and list mailboxes.

Production intake would read a shared mailbox (IMAP/Graph) that experts CC; this MVP accepts
.eml/JSON uploads and the bundled synthetic samples. Imports are restricted to development
until authentication exists, like every other write endpoint.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, SecretStr, StringConstraints
from sqlalchemy import func, select

from app.api.deps import DbSession, require_development
from app.models import CommunicationSource, ConversationThread, EmailConnection, Message
from app.models.enums import SourceType
from app.seed.demo_data import DEMO_MAILBOX, DEMO_SOURCES
from app.seed.demo_emails import load_demo_emails
from app.services.credentials import encrypt
from app.services.email_imap import ImapAccount, ImapError, check_account
from app.services.email_ingest import EmailParseError, import_emails, parse_eml, parse_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/email", tags=["integrations"])


class EmailIn(BaseModel):
    """Either `raw` (the full .eml text) or the JSON fields."""

    raw: Annotated[str, StringConstraints(max_length=200_000)] | None = None
    from_: str | None = Field(default=None, alias="from")
    subject: str | None = None
    date: str | None = None
    body: Annotated[str, StringConstraints(max_length=50_000)] | None = None
    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] | None = None


class EmailImportRequest(BaseModel):
    mailbox: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)] = DEMO_MAILBOX
    emails: list[EmailIn] = Field(min_length=1, max_length=50)


class EmailImportResponse(BaseModel):
    mailbox: str
    imported: int
    duplicates: int
    threads: list[dict[str, Any]]
    skipped_reason: str | None = None
    note: str = "Email threads are analyzed by the same discovery pipeline as chat (Gemini, debounced)."


class Mailbox(BaseModel):
    id: str
    name: str
    mailbox: str
    enabled: bool
    threads: int
    messages: int


def _schedule(request: Request, threads: list) -> None:
    engine = getattr(request.app.state, "discovery", None)
    for thread_id, title in threads:
        try:
            if engine is not None:
                engine.schedule_analysis(thread_id, title)
        except Exception:  # noqa: BLE001 - stored emails are analyzed later by re-analysis
            logger.exception("Could not schedule analysis for email thread %s", thread_id)


async def _import(db: DbSession, request: Request, mailbox: str, mails, source_name=None) -> EmailImportResponse:
    result = await import_emails(db, mailbox, mails, source_name=source_name)
    await db.commit()
    _schedule(request, result.threads)
    return EmailImportResponse(
        mailbox=mailbox, imported=result.imported, duplicates=result.duplicates,
        threads=[{"id": str(t), "title": title} for t, title in result.threads],
        skipped_reason=result.skipped_reason,
    )


@router.post("/import", response_model=EmailImportResponse, dependencies=[Depends(require_development)],
             summary="Import emails into a mailbox source (development only)")
async def import_email(body: EmailImportRequest, db: DbSession, request: Request) -> EmailImportResponse:
    mails = []
    for index, item in enumerate(body.emails, start=1):
        try:
            mails.append(parse_eml(item.raw) if item.raw else parse_json(item.model_dump(by_alias=True)))
        except EmailParseError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Email {index}: {exc}") from None
    return await _import(db, request, body.mailbox, mails)


@router.post("/import-samples", response_model=EmailImportResponse, dependencies=[Depends(require_development)],
             summary="Import the bundled synthetic demo emails (development only)")
async def import_samples(db: DbSession, request: Request) -> EmailImportResponse:
    return await _import(db, request, DEMO_MAILBOX, load_demo_emails(), source_name=DEMO_SOURCES["email"][0])


@router.get("/mailboxes", response_model=list[Mailbox], summary="Mailboxes used as knowledge sources")
async def mailboxes(db: DbSession) -> list[Mailbox]:
    rows = await db.execute(
        select(CommunicationSource,
               select(func.count()).select_from(ConversationThread)
               .where(ConversationThread.communication_source_id == CommunicationSource.id).scalar_subquery(),
               select(func.count()).select_from(Message).join(ConversationThread)
               .where(ConversationThread.communication_source_id == CommunicationSource.id).scalar_subquery())
        .where(CommunicationSource.source_type == SourceType.EMAIL)
        .order_by(CommunicationSource.created_at)
    )
    return [Mailbox(id=str(s.id), name=s.name, mailbox=s.external_source_id.removeprefix("mailbox:"),
                    enabled=s.enabled, threads=t or 0, messages=m or 0) for s, t, m in rows]


# ---- real mailboxes (IMAP) ----------------------------------------------------------------------

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ConnectionCreate(BaseModel):
    host: Short = "imap.gmail.com"
    port: int = Field(default=993, ge=1, le=65535)
    username: Short  # the email address
    password: SecretStr = Field(min_length=1, max_length=200)  # app password; stored encrypted
    folder: Short = "Elisa Echo"  # one folder / Gmail label; INBOX reads everything new
    since_days: int = Field(default=3, ge=1, le=30)
    max_per_poll: int = Field(default=10, ge=1, le=50)


class ConnectionUpdate(BaseModel):
    enabled: bool


class ConnectionRead(BaseModel):
    """Never includes the password."""

    id: uuid.UUID
    host: str
    port: int
    username: str
    folder: str
    since_days: int
    max_per_poll: int
    enabled: bool
    status: str
    last_error: str | None
    last_checked_at: datetime | None
    imported_count: int
    folder_message_count: int | None


class CheckResult(BaseModel):
    status: str
    fetched: int
    imported: int
    duplicates: int
    remaining: int
    threads: list[str]
    error: str | None


def _read(c: EmailConnection) -> ConnectionRead:
    return ConnectionRead(id=c.id, host=c.host, port=c.port, username=c.username, folder=c.folder,
                          since_days=c.since_days, max_per_poll=c.max_per_poll, enabled=c.enabled, status=c.status,
                          last_error=c.last_error, last_checked_at=c.last_checked_at,
                          imported_count=c.imported_count, folder_message_count=c.folder_message_count)


def _poller(request: Request):
    poller = getattr(request.app.state, "email_poller", None)
    if poller is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The email poller is not running.")
    return poller


@router.get("/connections", response_model=list[ConnectionRead], summary="Connected mailboxes (IMAP)")
async def list_connections(db: DbSession) -> list[ConnectionRead]:
    rows = await db.scalars(select(EmailConnection).order_by(EmailConnection.created_at))
    return [_read(c) for c in rows]


@router.post("/connections", response_model=ConnectionRead, dependencies=[Depends(require_development)],
             summary="Connect a mailbox folder over IMAP (development only)",
             responses={400: {"description": "Login failed or folder not found"}})
async def create_connection(body: ConnectionCreate, db: DbSession, request: Request) -> ConnectionRead:
    password = body.password.get_secret_value()
    account = ImapAccount(body.host, body.port, body.username, password, body.folder)
    try:
        count = await asyncio.to_thread(check_account, account)  # verify before storing anything
    except ImapError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    conn = await db.scalar(select(EmailConnection).where(
        EmailConnection.host == body.host, EmailConnection.username == body.username,
        EmailConnection.folder == body.folder))
    if conn is None:
        conn = EmailConnection(host=body.host, port=body.port, username=body.username, folder=body.folder,
                               password_encrypted="", imported_count=0)
        db.add(conn)
    conn.port, conn.since_days, conn.max_per_poll = body.port, body.since_days, body.max_per_poll
    conn.password_encrypted = encrypt(password)
    conn.enabled, conn.status, conn.last_error, conn.folder_message_count = True, "connected", None, count
    await db.commit()
    await db.refresh(conn)
    poller = getattr(request.app.state, "email_poller", None)
    if poller is not None:
        poller.check_soon(conn.id)  # first check right away
    return _read(conn)


@router.post("/connections/{connection_id}/check", response_model=CheckResult,
             dependencies=[Depends(require_development)], summary="Check the mailbox for new emails now")
async def check_now(connection_id: uuid.UUID, request: Request) -> CheckResult:
    outcome = await _poller(request).poll_now(connection_id)
    if outcome.status == "missing":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    return CheckResult(status=outcome.status, fetched=outcome.fetched, imported=outcome.imported,
                       duplicates=outcome.duplicates, remaining=outcome.remaining,
                       threads=[title for _, title in outcome.threads], error=outcome.error)


@router.patch("/connections/{connection_id}", response_model=ConnectionRead,
              dependencies=[Depends(require_development)], summary="Pause or resume a mailbox")
async def update_connection(connection_id: uuid.UUID, body: ConnectionUpdate, db: DbSession) -> ConnectionRead:
    conn = await db.get(EmailConnection, connection_id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    conn.enabled = body.enabled
    await db.commit()
    await db.refresh(conn)
    return _read(conn)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_development)],
               summary="Disconnect: deletes the stored password; imported emails and knowledge stay")
async def delete_connection(connection_id: uuid.UUID, db: DbSession) -> None:
    conn = await db.get(EmailConnection, connection_id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    await db.delete(conn)
    await db.commit()
