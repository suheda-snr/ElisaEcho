"""Seed script safety (no database)."""

import ast
import inspect
from datetime import UTC

import pytest

from app.core.config import Settings
from app.seed import demo_data, seed
from app.seed.seed import SeedNotAllowedError, ensure_seed_allowed, seed_demo_data


@pytest.mark.parametrize("environment", ["production", "staging", "prod", ""])
def test_seed_refuses_outside_development(environment: str) -> None:
    with pytest.raises(SeedNotAllowedError):
        ensure_seed_allowed(Settings(_env_file=None, environment=environment))


@pytest.mark.parametrize("environment", ["development", "test", "Development"])
def test_seed_allowed_in_development_and_test(environment: str) -> None:
    ensure_seed_allowed(Settings(_env_file=None, environment=environment))


async def test_seed_does_not_touch_the_database_in_production() -> None:
    class ExplodingSession:
        def __getattr__(self, name: str):
            raise AssertionError("seed touched the database in production")

    with pytest.raises(SeedNotAllowedError):
        await seed_demo_data(ExplodingSession(), Settings(_env_file=None, environment="production"))  # type: ignore[arg-type]


def test_seed_code_never_deletes() -> None:
    """No delete/drop calls and no destructive SQL anywhere in the seed code path."""
    import app.services.ingestion as ingestion

    destructive_names = {"delete", "drop_all", "drop", "truncate", "execute_delete"}
    destructive_sql = ("DELETE ", "TRUNCATE", "DROP ")
    for module in (seed, demo_data, ingestion):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id not in destructive_names, (module.__name__, node.id)
            elif isinstance(node, ast.Attribute):
                assert node.attr not in destructive_names, (module.__name__, node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(sql in node.value for sql in destructive_sql), module.__name__


def test_seed_stores_messages_not_extracted_knowledge() -> None:
    source = inspect.getsource(seed)
    for knowledge_model in ("KnowledgeItem", "KnowledgeCandidate", "KnowledgeEvidence"):
        assert knowledge_model not in source


def test_demo_data_is_clearly_synthetic_and_well_formed() -> None:
    threads = demo_data.DEMO_THREADS
    thread_ids = [t.external_id for t in threads]
    message_ids = [m.external_id for t in threads for m in t.messages]
    assert len(set(thread_ids)) == len(thread_ids)
    assert len(set(message_ids)) == len(message_ids)

    for thread in threads:
        assert thread.messages
        sent = [m.sent_at for m in thread.messages]
        assert sent == sorted(sent), thread.external_id
        for message in thread.messages:
            assert message.sent_at.tzinfo is UTC
            assert "(synthetic)" in message.author_name
            assert message.author_id.startswith("demo-")
            url = demo_data.demo_message_url(thread.external_id, message.external_id)
            assert ".invalid/" in url


def test_demo_data_covers_required_scenarios() -> None:
    scenarios = {t.scenario for t in demo_data.DEMO_THREADS}
    assert scenarios == {
        "confirmed_resolution",
        "irrelevant_chatter",
        "unresolved_problem",
        "multiple_suggested_fixes",
    }
    site42 = next(t for t in demo_data.DEMO_THREADS if t.scenario == "confirmed_resolution")
    assert site42.title == "Intermittent connectivity at Site 42"
