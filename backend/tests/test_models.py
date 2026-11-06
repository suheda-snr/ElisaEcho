"""Schema shape: tables, keys, constraints and ORM relationships (no database)."""

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect

import app.models as models
from app.db.base import Base

EXPECTED_TABLES = {
    "communication_sources",
    "conversation_threads",
    "messages",
    "knowledge_candidates",
    "knowledge_items",
    "knowledge_evidence",
    "equipment",
    "incidents",
    "knowledge_chunks",
    "knowledge_item_equipment",
    "knowledge_item_incidents",
}


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    sets = {
        tuple(c.name for c in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    sets |= {(c.name,) for c in table.columns if c.unique}
    return sets


def _foreign_key(table_name: str, column: str):
    (fk,) = Base.metadata.tables[table_name].columns[column].foreign_keys
    return fk


def test_all_tables_are_registered() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES - {"knowledge_item_equipment", "knowledge_item_incidents"}))
def test_entities_use_uuid_keys_and_aware_timestamps(table_name: str) -> None:
    table = Base.metadata.tables[table_name]
    assert [c.name for c in table.primary_key.columns] == ["id"]
    assert table.columns["id"].type.python_type.__name__ == "UUID"
    assert table.columns["created_at"].type.timezone is True


@pytest.mark.parametrize(
    ("table_name", "columns"),
    [
        ("communication_sources", ("source_type", "external_source_id")),
        ("conversation_threads", ("communication_source_id", "external_thread_id")),
        ("messages", ("thread_id", "external_message_id")),
        ("equipment", ("equipment_identifier",)),
        ("incidents", ("incident_number",)),
        ("knowledge_items", ("candidate_id",)),
        ("knowledge_chunks", ("knowledge_item_id", "chunk_index")),
        ("knowledge_evidence", ("knowledge_item_id", "message_id", "evidence_type")),
    ],
)
def test_unique_constraints(table_name: str, columns: tuple[str, ...]) -> None:
    assert columns in _unique_column_sets(table_name)


@pytest.mark.parametrize(
    ("table_name", "column", "target", "ondelete"),
    [
        ("conversation_threads", "communication_source_id", "communication_sources.id", "RESTRICT"),
        ("messages", "thread_id", "conversation_threads.id", "RESTRICT"),
        ("knowledge_candidates", "thread_id", "conversation_threads.id", "RESTRICT"),
        ("knowledge_items", "candidate_id", "knowledge_candidates.id", "SET NULL"),
        ("knowledge_evidence", "knowledge_item_id", "knowledge_items.id", "CASCADE"),
        # Evidence must never silently disappear because its message was removed.
        ("knowledge_evidence", "message_id", "messages.id", "RESTRICT"),
        ("knowledge_chunks", "knowledge_item_id", "knowledge_items.id", "CASCADE"),
        ("knowledge_item_equipment", "equipment_id", "equipment.id", "CASCADE"),
        ("knowledge_item_incidents", "incident_id", "incidents.id", "CASCADE"),
    ],
)
def test_foreign_keys(table_name: str, column: str, target: str, ondelete: str) -> None:
    fk = _foreign_key(table_name, column)
    assert fk.target_fullname == target
    assert fk.ondelete == ondelete


@pytest.mark.parametrize(
    ("model", "relationships"),
    [
        (models.CommunicationSource, {"threads"}),
        (models.ConversationThread, {"source", "messages", "knowledge_candidates"}),
        (models.Message, {"thread", "evidence"}),
        (models.KnowledgeCandidate, {"thread", "knowledge_item"}),
        (models.KnowledgeItem, {"candidate", "evidence", "chunks", "equipment", "incidents"}),
        (models.KnowledgeEvidence, {"knowledge_item", "message"}),
        (models.KnowledgeChunk, {"knowledge_item"}),
        (models.Equipment, {"knowledge_items"}),
        (models.Incident, {"knowledge_items"}),
    ],
)
def test_relationships(model: type, relationships: set[str]) -> None:
    assert relationships <= set(inspect(model).relationships.keys())


def test_knowledge_item_links_to_equipment_and_incidents_through_association_tables() -> None:
    rels = inspect(models.KnowledgeItem).relationships
    assert rels["equipment"].secondary.name == "knowledge_item_equipment"
    assert rels["incidents"].secondary.name == "knowledge_item_incidents"


def test_thread_messages_are_ordered_by_send_time() -> None:
    order_by = inspect(models.ConversationThread).relationships["messages"].order_by
    assert [c.name for c in order_by] == ["sent_at", "external_message_id"]


def test_embedding_column_uses_documented_dimension() -> None:
    column = Base.metadata.tables["knowledge_chunks"].columns["embedding"]
    assert models.EMBEDDING_DIMENSION == 768
    assert column.type.dim == models.EMBEDDING_DIMENSION
    assert column.nullable


def test_status_columns_are_constrained() -> None:
    expected = {
        ("communication_sources", "source_type"),
        ("conversation_threads", "processing_status"),
        ("knowledge_candidates", "detection_status"),
        ("knowledge_items", "resolution_status"),
        ("knowledge_items", "approval_status"),
        ("knowledge_evidence", "evidence_type"),
        ("incidents", "status"),
        ("incidents", "severity"),
    }
    for table_name, column in expected:
        column_type = Base.metadata.tables[table_name].columns[column].type
        assert column_type.native_enum is False and column_type.create_constraint, column


def test_confidence_is_range_checked() -> None:
    table = Base.metadata.tables["knowledge_candidates"]
    checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
    assert any("confidence" in str(c.sqltext) for c in checks)


def test_new_knowledge_is_unreviewed_by_default() -> None:
    column = Base.metadata.tables["knowledge_items"].columns["approval_status"]
    assert column.server_default.arg == "unreviewed"
