"""Prompts for pair comparison and group summaries."""

import json
from typing import Any

COMPARE_INSTRUCTION = """\
You compare two operational troubleshooting cases (A and B) that engineers discussed in
separate conversations. Decide how they relate, using ONLY the text provided.

Rules:
- Similar wording is not enough. Same symptoms with a different cause is `related_symptoms`.
- `same_problem` / `supporting_evidence`: same underlying problem; B confirms A's resolution
  or vice versa. Use `supporting_evidence` when one case independently confirms the other's fix.
- `same_problem_different_conditions`: same problem, but equipment, firmware, configuration,
  vendor or site differ in a way that may matter.
- `different_outcome`: the same action was tried with a different result.
- `potentially_conflicting`: the recommendations contradict each other.
- `unrelated`: different problems. Set is_related=false.
- Copy condition values (firmware versions, models, configuration names) exactly as written.
  If a value is not stated for a case, use null and list the condition under unknown_conditions.
  Never assume two cases share a firmware version or configuration.
- Never invent equipment, versions or outcomes.
- Cite messages with their refs: A-refs only in first_evidence_refs, B-refs only in
  second_evidence_refs.
"""

SUMMARY_INSTRUCTION = """\
You summarize a group of related operational troubleshooting cases (K1, K2, ...) from
separate engineer conversations. Use ONLY the text provided.

Rules:
- State the shared problem and symptoms.
- List each distinct resolution path with its reported outcome and the conditions under
  which it was reported, citing the cases (case_refs). Keep paths that worked under some
  conditions and failed under others separate, with their conditions.
- failed_attempts: actions reported as not working, with the condition if stated.
- contradictions: where cases disagree; never resolve them by guessing.
- missing_information: conditions that are needed to choose a path but are unknown for
  some cases (e.g. firmware version not stated).
- Copy firmware versions, models and identifiers exactly. Never invent them.
- A case may include troubleshooting_feedback: counts of later attempts reported by engineers
  (self-reported, not verified). Use it to note where a path worked or failed under which
  firmware/equipment (in solution conditions, failed_attempts, contradictions), always saying
  it is self-reported feedback. Never treat it as approval or invent counts.
- This is a draft for expert review, not an approved procedure.
"""


def compare_contents(a: dict[str, Any], b: dict[str, Any]) -> str:
    return "CASE A:\n" + json.dumps(a, ensure_ascii=False, indent=1) + \
        "\n\nCASE B:\n" + json.dumps(b, ensure_ascii=False, indent=1)


def summary_contents(cases: dict[str, dict[str, Any]], relations: list[str]) -> str:
    body = "\n\n".join(f"{label}:\n" + json.dumps(payload, ensure_ascii=False, indent=1)
                       for label, payload in cases.items())
    if relations:
        body += "\n\nAssessed relationships between cases:\n" + "\n".join(f"- {r}" for r in relations)
    return body
