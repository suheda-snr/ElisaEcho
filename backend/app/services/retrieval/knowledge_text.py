"""Searchable text for a knowledge item.

Only structured knowledge goes in (no author names, no raw chat). Evidence stays in
knowledge_evidence and is returned separately with search results. The output is
deterministic, so "did the text change?" is a plain string comparison.
"""

from collections.abc import Sequence
from typing import Any

from app.models.enums import ResolutionStatus

# Short items (all of the demo data) fit in one chunk; longer ones are split by section.
MAX_CHUNK_CHARS = 2400

_RESOLUTION_LABEL = {
    ResolutionStatus.CONFIRMED_IN_CONVERSATION: "confirmed in conversation",
    ResolutionStatus.SUGGESTED: "suggested, not confirmed",
    ResolutionStatus.UNKNOWN: "not confirmed",
}


def _join(values: Sequence[str]) -> str:
    return "; ".join(v.strip() for v in values if v and v.strip())


def _action_line(action: dict[str, Any]) -> str:
    outcome = str(action.get("outcome", "unknown")).replace("_", " ")
    return f"{action.get('action', '').strip()} ({outcome})"


def knowledge_sections(
    *,
    title: str,
    problem_description: str,
    symptoms: Sequence[str],
    root_cause: str | None,
    resolution: str | None,
    resolution_status: ResolutionStatus,
    attempted_actions: Sequence[dict[str, Any]],
    applicability_conditions: Sequence[str],
    equipment_identifiers: Sequence[str],
    incident_numbers: Sequence[str],
) -> list[str]:
    sections = [f"Title: {title.strip()}", f"Problem: {problem_description.strip()}"]
    if symptoms:
        sections.append(f"Symptoms: {_join(symptoms)}")
    if equipment_identifiers:
        sections.append(f"Equipment and sites: {_join(equipment_identifiers)}")
    if incident_numbers:
        sections.append(f"Incidents: {_join(incident_numbers)}")
    if root_cause:
        sections.append(f"Root cause: {root_cause.strip()}")
    if resolution:
        sections.append(f"Resolution ({_RESOLUTION_LABEL[resolution_status]}): {resolution.strip()}")
    if attempted_actions:
        sections.append(f"Attempted actions: {_join([_action_line(a) for a in attempted_actions])}")
    if applicability_conditions:
        sections.append(f"Applicability and warnings: {_join(applicability_conditions)}")
    return [s for s in sections if not s.endswith(": ")]


def split_into_chunks(sections: Sequence[str], max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Pack whole sections into chunks; every chunk after the first repeats the title line
    for context. Over-long single sections are cut at word boundaries. Duplicates dropped."""
    if not sections:
        return []
    header = sections[0]
    pieces: list[str] = []
    for section in sections:
        while len(section) > max_chars:
            cut = section.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            pieces.append(section[:cut].rstrip())
            section = section[cut:].lstrip()
        pieces.append(section)

    chunks: list[str] = []
    current: list[str] = []
    for piece in pieces:
        candidate = "\n".join([*current, piece])
        if current and len(candidate) > max_chars:
            chunks.append("\n".join(current))
            current = [header, piece] if piece != header else [piece]
        else:
            current.append(piece)
    if current:
        chunks.append("\n".join(current))

    unique: list[str] = []
    for chunk in chunks:
        if chunk not in unique:
            unique.append(chunk)
    return unique
