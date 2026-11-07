"""Scripted stand-in for Gemini consolidation calls (no API calls).

Cases are identified by a tag at the start of their title ("S42: ..."). Pair rules are keyed
by the unordered pair of tags; the fake orients values to whichever case the server put
first (A) and second (B), like a real model reading the prompt.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.ai.consolidation_schema import ConditionDifference, GroupSummaryDraft, PairComparison, SolutionPath
from app.ai.gemini import GeminiError


@dataclass
class Rule:
    relationship: str
    outcome: str = "same_outcome"
    # field -> {tag: value or None}
    conditions: dict[str, dict[str, str | None]] = field(default_factory=dict)
    unknown: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    # Override evidence refs (e.g. invalid ones); default cites the first message of each case.
    first_refs: list[str] | None = None
    second_refs: list[str] | None = None
    # Tag of the case the newer one makes outdated (None = no replacement).
    replaced: str | None = None


def tag(payload: dict[str, Any]) -> str:
    return payload["title"].split(":", 1)[0]


def parse_pair(contents: str) -> tuple[dict[str, Any], dict[str, Any]]:
    a, b = contents.removeprefix("CASE A:\n").split("\n\nCASE B:\n")
    return json.loads(a), json.loads(b)


class FakeConsolidationGemini:
    model = "fake-consolidation"
    configured = True

    def __init__(self, rules: dict[frozenset[str], Rule] | None = None,
                 summary: Callable[[str], GroupSummaryDraft] | None = None) -> None:
        self.rules = rules or {}
        self.summary = summary
        self.fail: GeminiError | None = None
        self.pair_calls: list[frozenset[str]] = []
        self.summary_calls: list[str] = []

    async def generate_structured(self, *, system_instruction: str, contents: str, schema: type) -> Any:
        if self.fail is not None:
            raise self.fail
        if schema is PairComparison:
            a, b = parse_pair(contents)
            key = frozenset({tag(a), tag(b)})
            self.pair_calls.append(key)
            return self._compare(a, b, self.rules.get(key))
        assert schema is GroupSummaryDraft
        self.summary_calls.append(contents)
        return self.summary(contents) if self.summary else default_summary(contents)

    @staticmethod
    def _compare(a: dict[str, Any], b: dict[str, Any], rule: Rule | None) -> PairComparison:
        if rule is None:
            rule = Rule("unrelated", outcome="not_comparable")
        ta, tb = tag(a), tag(b)
        return PairComparison(
            is_related=rule.relationship != "unrelated",
            relationship_type=rule.relationship,
            shared_symptoms=["customer sessions drop"],
            shared_equipment=rule.equipment,
            different_conditions=[ConditionDifference(field=name, first_value=v.get(ta), second_value=v.get(tb))
                                  for name, v in rule.conditions.items()],
            unknown_conditions=rule.unknown,
            outcome_comparison=rule.outcome,
            explanation=f"{ta} vs {tb}: {rule.relationship}",
            first_evidence_refs=rule.first_refs if rule.first_refs is not None else [a["messages"][0]["ref"]],
            second_evidence_refs=rule.second_refs if rule.second_refs is not None else [b["messages"][0]["ref"]],
            replaced_case="A" if rule.replaced == ta else "B" if rule.replaced == tb else "none",
        )


def default_summary(contents: str) -> GroupSummaryDraft:
    labels = [line.rstrip(":") for line in contents.splitlines() if line.startswith("K") and line.endswith(":")]
    return GroupSummaryDraft(
        title="Customers lose sessions behind site routers",
        shared_problem="Customer sessions drop every 20-30 minutes.",
        shared_symptoms=["customer sessions drop"],
        known_environment=["firmware 3.2", "firmware 4.0", "firmware 9.9"],  # 9.9 is invented
        solutions=[
            SolutionPath(description="Restart the DHCP relay service", outcome="mixed",
                         conditions=["worked on firmware 3.2", "failed on firmware 4.0"], case_refs=labels),
            SolutionPath(description="Not reported by any case", outcome="successful", conditions=[],
                         case_refs=["K99"]),
        ],
        failed_attempts=["Relay restart on firmware 4.0"],
        contradictions=["The relay restart worked in some cases and not in others."],
        missing_information=["Firmware version for Site 42"],
    )
