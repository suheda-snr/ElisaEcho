"""Email parsing, extraction of context fields, and supersession rules (no DB, no Gemini)."""

import uuid
from datetime import UTC, datetime, timedelta

from app.ai.consolidation_schema import PairComparison
from app.seed.demo_emails import load_demo_emails
from app.services.consolidation.validation import CaseView, validate_comparison
from app.services.discovery.validation import validate_analysis
from app.services.email_ingest import clean_body, normalize_subject, parse_eml, parse_json
from tests.discovery_fakes import analysis, ev

# ---- email ---------------------------------------------------------------------------------


def test_reply_keeps_only_the_authors_text_and_thread_headers() -> None:
    mails = {m.message_id: m for m in load_demo_emails()}
    reply = mails["<trn042-sfp-re1@network.elisa-echo.invalid>"]
    assert reply.in_reply_to == "<trn042-sfp-q@field-ops.elisa-echo.invalid>"
    assert reply.references == ["<trn042-sfp-q@field-ops.elisa-echo.invalid>"]
    assert "check the traffic counters" in reply.body
    assert "Should I replace the SFP again?" not in reply.body  # quoted original removed
    assert "wrote:" not in reply.body
    assert reply.from_address == "erkki.expert@network.elisa-echo.invalid"
    assert reply.sent_at == datetime(2026, 10, 5, 10, 2, tzinfo=UTC)


def test_signature_and_outlook_history_are_removed() -> None:
    assert clean_body("Key is at the depot.\n-- \nKaisa | Coordinator") == "Key is at the depot."
    outlook = "Use tag P3.\n\n-----Original Message-----\nFrom: someone\nold text"
    assert clean_body(outlook) == "Use tag P3."
    assert clean_body("> quoted\nmine") == "mine"


def test_subject_normalization_for_threading() -> None:
    assert normalize_subject("RE: Fwd: VS: TRN-042 traffic") == "trn-042 traffic"
    assert normalize_subject("AW:  TRN-042   traffic") == "trn-042 traffic"


def test_html_and_json_emails() -> None:
    raw = ("From: A <a@x.invalid>\nSubject: Hi\nDate: Mon, 05 Oct 2026 08:00:00 +0000\n"
           "Content-Type: text/html\n\n<p>Disable the interface<br>then enable it.</p>")
    assert "Disable the interface\nthen enable it." in parse_eml(raw).body
    parsed = parse_json({"from": "Erkki <e@x.invalid>", "subject": "RE: X", "date": "2026-10-05T10:00:00",
                         "body": "Check counters."})
    assert parsed.sent_at.tzinfo is not None and parsed.message_id.startswith("<generated-")
    again = parse_json({"from": "Erkki <e@x.invalid>", "subject": "RE: X", "date": "2026-10-05T10:00:00",
                        "body": "Check counters."})
    assert again.message_id == parsed.message_id  # deterministic: re-import is idempotent


# ---- extraction of context fields ------------------------------------------------------------

REFS = {"M1": uuid.uuid4(), "M2": uuid.uuid4()}
TEXT = ("Changed the SFP on transmission node TRN-042. These old units behave like this after an optical "
        "module replacement. Barrier at SITE-PELLO-03.")


def test_sites_and_events_must_be_in_the_conversation() -> None:
    raw = analysis(classification="confirmed_resolution", is_valuable_knowledge=True, title="t",
                   problem_description="p", resolution="Disable and enable the interface",
                   resolution_status="suggested", equipment_identifiers=["TRN-042"],
                   site_identifiers=["SITE-PELLO-03", "SITE-OULU-99"],
                   trigger_events=["SFP replacement", "firmware upgrade"], scope="same_equipment_class",
                   evidence=[ev("M1", "problem_report"), ev("M2", "suggested_solution")])
    valid = validate_analysis(raw, REFS, TEXT)
    assert valid.site_identifiers == ["SITE-PELLO-03"]
    assert valid.trigger_events == ["SFP replacement"]
    assert valid.scope == "same_equipment_class" and valid.knowledge_type == "troubleshooting"
    assert any("firmware upgrade" in f for f in valid.flags)


def test_class_scope_needs_a_device_and_access_info_becomes_site_access() -> None:
    raw = analysis(classification="access_information", is_valuable_knowledge=True, title="Barrier key",
                   problem_description="Locked barrier", resolution="Key at the depot", resolution_status="suggested",
                   scope="same_equipment_class", evidence=[ev("M1", "problem_report")])
    valid = validate_analysis(raw, REFS, TEXT)
    assert valid.scope == "unknown"  # no equipment to take a unit class from
    assert valid.knowledge_type == "site_access" and valid.creates_knowledge_item


# ---- supersession ----------------------------------------------------------------------------

T0 = datetime(2025, 3, 12, tzinfo=UTC)
OLD = CaseView(uuid.uuid4(), {"A1": uuid.uuid4()}, "lockbox code 4471", latest_at=T0)
NEW = CaseView(uuid.uuid4(), {"B1": uuid.uuid4()}, "key at the Pello depot", latest_at=T0 + timedelta(days=600))


def pair(replaced: str, **kw) -> PairComparison:
    base = dict(is_related=True, relationship_type="same_problem", shared_symptoms=[], shared_equipment=[],
                different_conditions=[], unknown_conditions=[], outcome_comparison="different_outcome",
                explanation="The lock was replaced; the lockbox is gone.", first_evidence_refs=["A1"],
                second_evidence_refs=["B1"], replaced_case=replaced)
    base.update(kw)
    return PairComparison(**base)


def test_newer_case_can_replace_older_one() -> None:
    assert validate_comparison(pair("A"), OLD, NEW).superseded == "first"


def test_replacement_by_an_older_case_is_rejected() -> None:
    valid = validate_comparison(pair("B"), OLD, NEW)  # claims the newer one is outdated
    assert valid.superseded is None and any("not newer" in n for n in valid.notes)


def test_replacement_needs_evidence_on_both_sides() -> None:
    valid = validate_comparison(pair("A", second_evidence_refs=["Z9"]), OLD, NEW)
    assert valid.superseded is None
    assert validate_comparison(pair("none"), OLD, NEW).superseded is None
