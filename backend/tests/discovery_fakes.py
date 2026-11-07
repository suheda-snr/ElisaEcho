"""Test doubles for Gemini. No test ever calls the real Gemini API."""

import re
from collections.abc import Callable
from typing import Any

from app.ai.analysis_schema import ThreadAnalysis
from app.ai.gemini import GeminiError


def analysis(**overrides: Any) -> ThreadAnalysis:
    data: dict[str, Any] = {
        "classification": "irrelevant",
        "is_valuable_knowledge": False,
        "title": None,
        "problem_description": None,
        "symptoms": [],
        "root_cause": None,
        "equipment_identifiers": [],
        "incident_numbers": [],
        "attempted_actions": [],
        "resolution": None,
        "resolution_status": "unknown",
        "applicability_conditions": [],
        "missing_information": [],
        "evidence": [],
        "confidence": 0.9,
        "rationale": "test",
    }
    data.update(overrides)
    return ThreadAnalysis.model_validate(data)


def ev(ref: str, kind: str, why: str = "supports it") -> dict[str, str]:
    return {"message_ref": ref, "evidence_type": kind, "explanation": why}


def act(action: str, outcome: str, *refs: str) -> dict[str, Any]:
    return {"action": action, "outcome": outcome, "message_refs": list(refs)}


IRRELEVANT = analysis(rationale="Lunch planning only.")


def site42_suggested() -> ThreadAnalysis:
    """What a model should say after the first two Site 42 messages."""
    return analysis(
        classification="unverified_suggestion",
        is_valuable_knowledge=True,
        title="Restart the affected service instead of rebooting the router",
        problem_description="Intermittent connectivity at Site 42",
        symptoms=["Connections drop every 20-30 minutes"],
        equipment_identifiers=["S42-RTR-01"],
        attempted_actions=[act("Reboot router", "unsuccessful", "M1"),
                           act("Restart DHCP relay service", "not_attempted", "M2")],
        resolution="Restart the DHCP relay service on S42-RTR-01",
        resolution_status="suggested",
        applicability_conditions=["Do not reboot the whole router"],
        missing_information=["Router model"],
        evidence=[ev("M1", "problem_report"), ev("M2", "suggested_solution")],
        confidence=0.7,
    )


def site42_confirmed() -> ThreadAnalysis:
    return analysis(
        classification="confirmed_resolution",
        is_valuable_knowledge=True,
        title="Restart the affected service instead of rebooting the router",
        problem_description="Intermittent connectivity at Site 42",
        symptoms=["Connections drop every 20-30 minutes"],
        equipment_identifiers=["S42-RTR-01"],
        attempted_actions=[act("Reboot router", "unsuccessful", "M1"),
                           act("Restart DHCP relay service", "successful", "M2", "M3", "M4")],
        resolution="Restart the DHCP relay service on S42-RTR-01",
        resolution_status="confirmed_in_conversation",
        applicability_conditions=["Do not reboot the whole router"],
        missing_information=["Router model"],
        evidence=[ev("M1", "problem_report"), ev("M2", "suggested_solution"),
                  ev("M4", "confirmed_resolution")],
        confidence=0.93,
    )


def message_count(contents: str) -> int:
    return len(re.findall(r'"ref": "M\d+"', contents))


class FakeGemini:
    """Returns `responder(contents)` (a ThreadAnalysis) or raises it if it is an exception."""

    model = "fake-gemini"
    configured = True

    def __init__(self, responder: Callable[[str], ThreadAnalysis | GeminiError] | ThreadAnalysis | GeminiError):
        self._responder = responder
        self.calls: list[str] = []

    async def generate_structured(self, *, system_instruction: str, contents: str, schema: type) -> Any:
        self.calls.append(contents)
        result = self._responder(contents) if callable(self._responder) else self._responder
        if isinstance(result, Exception):
            raise result
        return result
