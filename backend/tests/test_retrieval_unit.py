"""Phase 4 unit tests: text preparation, embeddings, identifiers, fusion, validation (no DB)."""

import math
import uuid

import httpx
import pytest

from app.ai.embeddings import (
    EmbeddingDimensionError,
    EmbeddingService,
    prepare_request,
    validate_and_normalize,
)
from app.models.enums import ResolutionStatus
from app.services.retrieval.knowledge_text import knowledge_sections, split_into_chunks
from app.services.retrieval.search import extract_identifiers, fuse, keyword_text

DIM = 768


def sections(**overrides):
    data = dict(
        title="Restart the DHCP relay service, not the router",
        problem_description="Intermittent connectivity at Site 42",
        symptoms=["Connections drop every 20-30 minutes"],
        root_cause=None,
        resolution="Restart the DHCP relay service on S42-RTR-01",
        resolution_status=ResolutionStatus.CONFIRMED_IN_CONVERSATION,
        attempted_actions=[{"action": "Reboot router", "outcome": "unsuccessful", "message_ids": ["x"]}],
        applicability_conditions=["Do not reboot the whole router"],
        equipment_identifiers=["S42-RTR-01"],
        incident_numbers=["INC-1042"],
    )
    data.update(overrides)
    return knowledge_sections(**data)


# ---- knowledge text ----------------------------------------------------------------------

def test_knowledge_text_contains_structured_fields_only() -> None:
    text = "\n".join(sections())
    for expected in ("Title: Restart the DHCP relay", "Problem: Intermittent connectivity at Site 42",
                     "Symptoms: Connections drop", "Equipment and sites: S42-RTR-01", "Incidents: INC-1042",
                     "Resolution (confirmed in conversation): Restart the DHCP relay service",
                     "Attempted actions: Reboot router (unsuccessful)",
                     "Applicability and warnings: Do not reboot the whole router"):
        assert expected in text
    assert "Root cause" not in text  # empty fields are omitted
    assert "message_ids" not in text and "x)" not in text  # evidence references stay separate


def test_knowledge_text_is_deterministic_and_marks_unconfirmed_fixes() -> None:
    assert sections() == sections()
    suggested = "\n".join(sections(resolution_status=ResolutionStatus.SUGGESTED))
    assert "Resolution (suggested, not confirmed)" in suggested


def test_short_items_become_one_chunk() -> None:
    assert len(split_into_chunks(sections())) == 1


def test_long_items_are_split_keeping_the_title_context() -> None:
    long = sections(symptoms=[f"symptom number {i} with some descriptive words" for i in range(150)])
    chunks = split_into_chunks(long, max_chars=600)
    assert len(chunks) > 1
    assert all(len(c) <= 600 + len(long[0]) + 1 for c in chunks)
    assert all(c.startswith("Title: Restart the DHCP relay") for c in chunks)
    assert len(set(chunks)) == len(chunks)


def test_identical_sections_produce_no_duplicate_chunks() -> None:
    chunks = split_into_chunks(["Title: A", "Problem: B", "Title: A"], max_chars=12)
    assert len(chunks) == len(set(chunks))  # the repeated section is not embedded twice
    assert chunks == ["Title: A", "Title: A\nProblem: B"]  # later chunks keep the title context


# ---- embeddings --------------------------------------------------------------------------

def test_embedding_2_uses_documented_text_prefixes() -> None:
    content, config = prepare_request("gemini-embedding-2", "router down", "query", DIM)
    assert content == "task: search result | query: router down"
    assert config.output_dimensionality == DIM and config.task_type is None
    content, _ = prepare_request("gemini-embedding-2", "fix", "document", DIM, title="Site 42")
    assert content == "title: Site 42 | text: fix"
    content, _ = prepare_request("gemini-embedding-2", "fix", "document", DIM)
    assert content == "title: none | text: fix"


def test_embedding_001_uses_task_types() -> None:
    content, config = prepare_request("gemini-embedding-001", "router down", "query", DIM)
    assert content == "router down" and config.task_type == "RETRIEVAL_QUERY"
    _, config = prepare_request("gemini-embedding-001", "fix", "document", DIM, title="T")
    assert config.task_type == "RETRIEVAL_DOCUMENT" and config.title == "T"
    assert config.output_dimensionality == DIM


def test_dimension_is_validated_and_vectors_normalized() -> None:
    with pytest.raises(EmbeddingDimensionError):
        validate_and_normalize([0.1] * 3072, DIM)
    with pytest.raises(EmbeddingDimensionError):
        validate_and_normalize([0.0] * DIM, DIM)
    vector = validate_and_normalize([0.5] * DIM, DIM)
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)


class CountingGemini:
    configured = True

    def __init__(self, values=None):
        self.calls = []
        self.values = values or [0.3] * DIM

    async def embed_content(self, *, model, text, config):
        self.calls.append(text)
        return self.values


async def test_query_embeddings_are_cached() -> None:
    gemini = CountingGemini()
    service = EmbeddingService(gemini, model="gemini-embedding-2")  # type: ignore[arg-type]
    first = await service.embed_query("Router keeps   dropping")
    second = await service.embed_query("router keeps dropping")
    assert first == second and len(gemini.calls) == 1


async def test_wrong_dimension_from_model_is_rejected() -> None:
    service = EmbeddingService(CountingGemini(values=[0.1] * 3072), model="gemini-embedding-2")  # type: ignore[arg-type]
    with pytest.raises(EmbeddingDimensionError):
        await service.embed_document("text")


# ---- identifiers and fusion --------------------------------------------------------------

def test_identifier_extraction_and_normalization() -> None:
    assert extract_identifiers("Is INC-1042 related to Site 42 and S42-RTR-01?") == ["inc1042", "site42", "s42rtr01"]
    assert extract_identifiers("PE-03 bgp flap on pe03") == ["pe03"]
    assert extract_identifiers("connection keeps dropping") == []


def test_bare_numbers_are_removed_from_keyword_query() -> None:
    assert keyword_text("timers 300 ms x 3 on PE-03").split() == ["timers", "ms", "x", "on", "PE-"]


def test_rrf_combines_ranks_and_prioritizes_exact_identifiers() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ranked = fuse(semantic=[(a, 0.9), (b, 0.8)], keyword=[(b, 0.5), (a, 0.4)], identifier=[(c, ["inc1042"])])
    assert ranked[0].item_id == c  # exact identifier match outranks fuzzy matches
    assert {r.item_id for r in ranked} == {a, b, c}  # deduplicated
    by_id = {r.item_id: r for r in ranked}
    assert by_id[a].semantic.rank == 1 and by_id[a].keyword.rank == 2
    assert by_id[c].matched_identifiers == ["inc1042"] and by_id[c].semantic is None
    assert math.isclose(by_id[a].score, 1 / 61 + 1 / 62)


def test_rrf_does_not_compare_raw_scores() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    # Huge keyword score vs. tiny similarity: only ranks matter.
    ranked = fuse(semantic=[(a, 0.01)], keyword=[(b, 999.0)], identifier=[])
    assert math.isclose(ranked[0].score, ranked[1].score)


# ---- endpoint validation -----------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"query": "a"}, {"query": "   "}, {"query": "x" * 501}, {"query": "router", "limit": 0},
    {"query": "router", "limit": 21}, {"query": "router", "filters": {"approval_status": "maybe"}},
    {"query": "router", "filters": {"resolution_status": "fixed"}}, {},
])
async def test_search_request_validation(client_without_db_access: httpx.AsyncClient, body: dict) -> None:
    assert (await client_without_db_access.post("/api/search", json=body)).status_code == 422


async def test_search_without_database_returns_503(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/search", json={"query": "router keeps dropping"})
    assert response.status_code == 503




def test_tied_keyword_scores_share_a_rank_and_meaning_breaks_ties() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    # Same keyword score: neither may win the keyword list by accident; closer meaning wins.
    ranked = fuse(semantic=[(a, 0.79), (b, 0.73)], keyword=[(b, 0.29), (a, 0.29)], identifier=[])
    assert ranked[0].item_id == a
    assert ranked[0].keyword.rank == ranked[1].keyword.rank == 1
