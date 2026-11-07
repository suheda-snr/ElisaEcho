"""Real-mailbox (IMAP) connections: verification, encrypted storage, read-only polling.

Uses an in-memory fake IMAP server and the isolated test database (no network, no Gemini).
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import EmailConnection, Message
from app.services import email_imap
from app.services.credentials import decrypt
from app.services.email_imap import EmailPoller, poll_connection
from tests.imap_fakes import PASSWORD, FakeMailbox, demo_folder

TODAY = datetime.now(UTC).date()


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch) -> FakeMailbox:
    box = FakeMailbox({"Elisa Echo": demo_folder(TODAY), "INBOX": []})
    monkeypatch.setattr(email_imap.imaplib, "IMAP4_SSL", box.factory)
    return box


@pytest.fixture
def poller(db_session: AsyncSession):
    @asynccontextmanager
    async def factory():
        yield db_session

    scheduled: list = []
    instance = EmailPoller(factory, lambda thread_id, title: scheduled.append(title), 3600)
    instance.scheduled = scheduled
    previous = getattr(app.state, "email_poller", None)
    app.state.email_poller = instance
    yield instance
    app.state.email_poller = previous


def connect_body(**kw) -> dict:
    return {"username": "demo.engineer@gmail.invalid", "password": PASSWORD, "folder": "Elisa Echo", **kw}


async def test_connect_verifies_login_and_never_returns_the_password(
    api: httpx.AsyncClient, db_session: AsyncSession, mailbox: FakeMailbox, poller: EmailPoller
) -> None:
    r = await api.post("/api/integrations/email/connections", json=connect_body())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "connected" and body["folder_message_count"] == 3
    await poller.drain()
    assert PASSWORD not in r.text and "password" not in body
    listed = await api.get("/api/integrations/email/connections")
    assert PASSWORD not in listed.text
    row = await db_session.get(EmailConnection, uuid.UUID(body["id"]))
    assert row.password_encrypted != PASSWORD and decrypt(row.password_encrypted) == PASSWORD


async def test_wrong_password_or_folder_stores_nothing(
    api: httpx.AsyncClient, db_session: AsyncSession, mailbox: FakeMailbox, poller: EmailPoller
) -> None:
    r = await api.post("/api/integrations/email/connections", json=connect_body(password="wrong"))
    assert r.status_code == 400 and "app password" in r.json()["detail"]
    r = await api.post("/api/integrations/email/connections", json=connect_body(folder="Nope"))
    assert r.status_code == 400 and "Elisa Echo" in r.json()["detail"]  # lists available folders
    r = await api.post("/api/integrations/email/connections", json=connect_body(host="unreachable.invalid"))
    assert r.status_code == 400 and "Could not reach" in r.json()["detail"]
    assert await db_session.scalar(select(func.count()).select_from(EmailConnection)) == 0


async def test_poll_imports_new_emails_once_and_read_only(
    api: httpx.AsyncClient, db_session: AsyncSession, mailbox: FakeMailbox, poller: EmailPoller
) -> None:
    conn_id = (await api.post("/api/integrations/email/connections",
                              json=connect_body(max_per_poll=2))).json()["id"]
    await poller.drain()  # the first check runs right after connecting
    assert mailbox.fetched == [101, 102]
    second = (await api.post(f"/api/integrations/email/connections/{conn_id}/check")).json()
    assert second["fetched"] == 1 and second["remaining"] == 0
    third = (await api.post(f"/api/integrations/email/connections/{conn_id}/check")).json()
    assert third["fetched"] == 0  # nothing new: the "UID n:*" quirk does not re-import the last one
    assert mailbox.fetched == [101, 102, 103]
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 3
    assert len(poller.scheduled) >= 2  # email threads handed to discovery

    # A new email arrives in the label.
    raw = (b"From: Erkki <e@x.invalid>\r\nSubject: TRN-118 same issue\r\nDate: "
           + datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000").encode()
           + b"\r\nMessage-ID: <new@x.invalid>\r\n\r\nCounters zero again, bounced the port.")
    mailbox.folders["Elisa Echo"].append((104, TODAY, raw))
    fourth = (await api.post(f"/api/integrations/email/connections/{conn_id}/check")).json()
    assert fourth["fetched"] == 1 and fourth["threads"] == ["TRN-118 same issue"]
    row = await db_session.get(EmailConnection, uuid.UUID(conn_id))
    await db_session.refresh(row)
    assert row.imported_count == 4 and row.last_uid == 104


async def test_only_recent_emails_on_first_check_and_uidvalidity_reset(
    db_session: AsyncSession, mailbox: FakeMailbox, poller: EmailPoller
) -> None:
    from app.services.credentials import encrypt

    old = TODAY - timedelta(days=40)
    mailbox.folders["Elisa Echo"] = [(u, old if u == 101 else d, r) for u, d, r in demo_folder(TODAY)]
    conn = EmailConnection(host="imap.gmail.com", port=993, username="u@gmail.invalid", folder="Elisa Echo",
                           password_encrypted=encrypt(PASSWORD), since_days=3, max_per_poll=10, imported_count=0,
                           enabled=True, status="connected")
    db_session.add(conn)
    await db_session.commit()

    @asynccontextmanager
    async def factory():
        yield db_session

    outcome = await poll_connection(factory, conn.id)
    assert outcome.fetched == 2 and 101 not in mailbox.fetched  # older than since_days: skipped
    mailbox.uid_validity = 8  # folder recreated on the server
    again = await poll_connection(factory, conn.id)
    assert again.fetched == 2 and again.imported == 0 and again.duplicates == 2  # re-read, not duplicated


async def test_disabled_and_deleted_connections(
    api: httpx.AsyncClient, db_session: AsyncSession, mailbox: FakeMailbox, poller: EmailPoller
) -> None:
    conn_id = (await api.post("/api/integrations/email/connections", json=connect_body())).json()["id"]
    await poller.drain()
    paused = await api.patch(f"/api/integrations/email/connections/{conn_id}", json={"enabled": False})
    assert paused.json()["enabled"] is False
    assert (await api.post(f"/api/integrations/email/connections/{conn_id}/check")).json()["status"] == "disabled"
    assert (await api.delete(f"/api/integrations/email/connections/{conn_id}")).status_code == 204
    assert await db_session.scalar(select(func.count()).select_from(EmailConnection)) == 0


async def test_connecting_is_development_only(api: httpx.AsyncClient, mailbox: FakeMailbox) -> None:
    from app.core.config import Settings, get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="production")
    try:
        r = await api.post("/api/integrations/email/connections", json=connect_body())
        assert r.status_code == 403
    finally:
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="test")


def test_imap_dates_are_locale_independent() -> None:
    assert email_imap._imap_date(date(2026, 11, 7)) == "07-Nov-2026"
