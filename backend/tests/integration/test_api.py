"""API endpoints returning real database records."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Equipment, Incident, KnowledgeEvidence, KnowledgeItem, Message
from app.models.enums import EvidenceType, ResolutionStatus
from app.seed.demo_data import DEMO_SOURCE_EXTERNAL_ID, DEMO_THREADS
from app.seed.seed import seed_demo_data


async def _seed(db_session: AsyncSession, settings: Settings) -> None:
    await seed_demo_data(db_session, settings)
    await db_session.flush()


async def _demo_threads(api: httpx.AsyncClient) -> list[dict]:
    sources = (await api.get("/api/sources")).json()["items"]
    demo = next(s for s in sources if s["external_source_id"] == DEMO_SOURCE_EXTERNAL_ID)
    return (await api.get(f"/api/threads?source_id={demo['id']}")).json()["items"]


async def test_db_health_ok_with_pgvector(api: httpx.AsyncClient) -> None:
    response = await api.get("/api/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected", "pgvector": True, "detail": None}


async def test_sources_create_list_and_conflict(api: httpx.AsyncClient) -> None:
    payload = {"name": "NOC Slack (test)", "source_type": "slack", "external_source_id": "T-API-TEST"}
    created = await api.post("/api/sources", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "NOC Slack (test)" and body["enabled"] is True
    uuid.UUID(body["id"])

    duplicate = await api.post("/api/sources", json=payload)
    assert duplicate.status_code == 409

    listed = (await api.get("/api/sources?limit=100")).json()
    assert body["id"] in {s["id"] for s in listed["items"]}
    assert listed["total"] >= 1


async def test_threads_list_and_detail(
    api: httpx.AsyncClient, db_session: AsyncSession, test_settings: Settings
) -> None:
    await _seed(db_session, test_settings)
    threads = await _demo_threads(api)
    assert len(threads) == len([t for t in DEMO_THREADS if t.source == "chat"])  # this source only
    # Newest conversation first.
    last_times = [t["last_message_at"] for t in threads]
    assert last_times == sorted(last_times, reverse=True)

    site42 = next(t for t in threads if t["title"] == "Intermittent connectivity at Site 42")
    assert site42["message_count"] == 4
    assert site42["processing_status"] == "pending"

    detail = await api.get(f"/api/threads/{site42['id']}")
    assert detail.status_code == 200
    assert detail.json()["source"]["external_source_id"] == DEMO_SOURCE_EXTERNAL_ID

    pending = (await api.get("/api/threads?processing_status=pending&limit=100")).json()
    assert {t["id"] for t in threads} <= {t["id"] for t in pending["items"]}
    processed = (await api.get("/api/threads?processing_status=processed&limit=100")).json()
    assert not {t["id"] for t in threads} & {t["id"] for t in processed["items"]}


async def test_thread_messages_in_order_with_pagination(
    api: httpx.AsyncClient, db_session: AsyncSession, test_settings: Settings
) -> None:
    await _seed(db_session, test_settings)
    site42 = next(t for t in await _demo_threads(api) if t["title"].startswith("Intermittent"))

    page1 = (await api.get(f"/api/threads/{site42['id']}/messages?limit=2")).json()
    page2 = (await api.get(f"/api/threads/{site42['id']}/messages?limit=2&offset=2")).json()
    assert page1["total"] == page2["total"] == 4
    messages = page1["items"] + page2["items"]
    assert [m["external_message_id"] for m in messages] == ["site42-m01", "site42-m02", "site42-m03", "site42-m04"]
    assert messages[0]["content"].startswith("Site 42 keeps dropping connections")
    assert messages[-1]["content"].startswith("That worked")
    assert all(m["source_url"] for m in messages)


async def test_unknown_ids_return_404(api: httpx.AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await api.get(f"/api/threads/{missing}")).status_code == 404
    assert (await api.get(f"/api/threads/{missing}/messages")).status_code == 404
    assert (await api.get(f"/api/knowledge/{missing}")).status_code == 404


async def test_knowledge_list_and_detail_with_evidence(
    api: httpx.AsyncClient, db_session: AsyncSession, test_settings: Settings
) -> None:
    await _seed(db_session, test_settings)
    site42 = next(t for t in await _demo_threads(api) if t["title"].startswith("Intermittent"))
    messages = (await api.get(f"/api/threads/{site42['id']}/messages")).json()["items"]
    report = await db_session.get(Message, uuid.UUID(messages[0]["id"]))
    confirm = await db_session.get(Message, uuid.UUID(messages[-1]["id"]))

    # Stand-in for what Phase 3 will extract automatically.
    item = KnowledgeItem(
        title="API test: restart the service, not the router",
        problem_description="Intermittent connectivity",
        resolution="Restart the DHCP relay service",
        resolution_status=ResolutionStatus.CONFIRMED_IN_CONVERSATION,
        evidence=[
            KnowledgeEvidence(message=report, evidence_type=EvidenceType.PROBLEM_REPORT),
            KnowledgeEvidence(message=confirm, evidence_type=EvidenceType.CONFIRMED_RESOLUTION),
        ],
        equipment=[Equipment(equipment_identifier="TEST-API-RTR")],
        incidents=[Incident(incident_number="TEST-API-INC", title="Outage", occurred_at=datetime(2026, 10, 14, tzinfo=UTC))],
    )
    db_session.add(item)
    await db_session.flush()

    listed = (await api.get("/api/knowledge?resolution_status=confirmed_in_conversation&limit=100")).json()
    assert str(item.id) in {k["id"] for k in listed["items"]}
    unreviewed = (await api.get("/api/knowledge?approval_status=approved&limit=100")).json()
    assert str(item.id) not in {k["id"] for k in unreviewed["items"]}

    detail = await api.get(f"/api/knowledge/{item.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["approval_status"] == "unreviewed"
    assert {e["evidence_type"] for e in body["evidence"]} == {"problem_report", "confirmed_resolution"}
    assert {e["message"]["id"] for e in body["evidence"]} == {messages[0]["id"], messages[-1]["id"]}
    assert all(e["message"]["source_url"] for e in body["evidence"])
    assert body["equipment"][0]["equipment_identifier"] == "TEST-API-RTR"
    assert body["incidents"][0]["incident_number"] == "TEST-API-INC"
