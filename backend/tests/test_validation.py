"""Pydantic schemas and request validation (no database)."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app
from app.models.enums import SourceType
from app.schemas.sources import SourceCreate
from app.schemas.threads import MessageIngest, ThreadIngest


def test_source_create_strips_and_validates() -> None:
    source = SourceCreate(name="  NOC Slack  ", source_type="slack", external_source_id=" T123 ")
    assert source.name == "NOC Slack"
    assert source.source_type is SourceType.SLACK
    assert source.external_source_id == "T123"
    assert source.enabled is True


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "source_type": "slack", "external_source_id": "x"},
        {"name": "   ", "source_type": "slack", "external_source_id": "x"},
        {"name": "ok", "source_type": "irc", "external_source_id": "x"},
        {"name": "ok", "source_type": "slack", "external_source_id": ""},
        {"name": "x" * 201, "source_type": "slack", "external_source_id": "x"},
        {"name": "ok", "source_type": "slack"},
    ],
)
def test_source_create_rejects_invalid_input(payload: dict) -> None:
    with pytest.raises(ValidationError):
        SourceCreate(**payload)


def _message(**overrides) -> dict:
    data = {
        "external_message_id": "m1",
        "author_external_id": "u1",
        "content": "Router is down",
        "sent_at": datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
    }
    data.update(overrides)
    return data


def test_message_ingest_accepts_aware_timestamps() -> None:
    message = MessageIngest(**_message())
    assert message.sent_at.tzinfo is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"sent_at": datetime(2026, 10, 1, 8, 0)},  # naive timestamp: ordering ambiguous
        {"content": ""},
        {"external_message_id": ""},
        {"author_external_id": "  "},
        {"edited_at": datetime(2026, 10, 1, 9, 0)},
    ],
)
def test_message_ingest_rejects_invalid_messages(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        MessageIngest(**_message(**overrides))


def test_thread_ingest_requires_external_id() -> None:
    with pytest.raises(ValidationError):
        ThreadIngest(external_thread_id="")


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
async def test_pagination_limits_are_enforced(
    client_without_db_access: httpx.AsyncClient, query: str
) -> None:
    response = await client_without_db_access.get(f"/api/threads?{query}")
    assert response.status_code == 422


async def test_invalid_ids_and_filters_are_rejected(
    client_without_db_access: httpx.AsyncClient,
) -> None:
    assert (await client_without_db_access.get("/api/threads/not-a-uuid")).status_code == 422
    assert (await client_without_db_access.get("/api/knowledge/123")).status_code == 422
    assert (
        await client_without_db_access.get("/api/threads?processing_status=bogus")
    ).status_code == 422
    assert (
        await client_without_db_access.get(f"/api/threads?source_id={uuid.uuid4()}x")
    ).status_code == 422


async def test_create_source_rejects_invalid_body(
    client_without_db_access: httpx.AsyncClient,
) -> None:
    response = await client_without_db_access.post(
        "/api/sources", json={"name": "", "source_type": "fax", "external_source_id": "x"}
    )
    assert response.status_code == 422


async def test_create_source_is_blocked_outside_development(
    client_without_db_access: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, environment="production")
    response = await client_without_db_access.post(
        "/api/sources", json={"name": "NOC", "source_type": "slack", "external_source_id": "T1"}
    )
    assert response.status_code == 403
