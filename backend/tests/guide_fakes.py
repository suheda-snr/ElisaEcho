"""Helpers to build Gemini guide drafts in tests (no API calls)."""

from typing import Any

from app.ai.guide_schema import GuideDraft


def node(id: str, node_type: str, title: str = "", **kw: Any) -> dict[str, Any]:
    return {
        "id": id, "node_type": node_type, "title": title or f"{node_type} {id}",
        "description": kw.get("description"), "question": kw.get("question"),
        "applicability_conditions": kw.get("applicability", []), "knowledge_refs": kw.get("k", []),
        "evidence_refs": kw.get("e", []), "conflict_note": kw.get("conflict"),
    }


def edge(source: str, target: str, label: str, condition: str | None = None) -> dict[str, Any]:
    return {"source": source, "target": target, "answer_label": label, "condition": condition}


def draft(nodes: list[dict], edges: list[dict], **kw: Any) -> GuideDraft:
    return GuideDraft.model_validate({
        "sufficient_evidence": kw.get("sufficient", True),
        "insufficiency_reason": kw.get("reason"),
        "title": kw.get("title", "Intermittent connectivity"),
        "summary": kw.get("summary", "Decide between known fixes."),
        "nodes": nodes, "edges": edges,
        "conflicts": kw.get("conflicts", []), "uncertainties": kw.get("uncertainties", []),
    })


def two_expert_draft(k1: str = "K1", k2: str = "K2", e1: str = "E1", e2: str = "E2",
                     e3: str = "E3", e4: str = "E4") -> GuideDraft:
    """Start -> did restarting the relay help? -> two expert branches + escalation."""
    return draft(
        [
            node("n1", "start", "Customer connections drop periodically"),
            node("n2", "question", "Relay restart already tried?",
                 question="Has restarting the DHCP relay service already been tried?"),
            node("n3", "recommendation", "Restart the DHCP relay service", k=[k1], e=[e1, e2],
                 applicability=["Do not reboot the whole router"]),
            node("n4", "diagnostic", "Check the DHCP lease time", k=[k2], e=[e3, e4],
                 question="Is the lease time unusually short (e.g. 60 seconds)?",
                 conflict="On S17-RTR-02 the relay restart did not help, unlike Site 42."),
            node("n5", "resolution", "Connection stable", k=[k1], e=[e2]),
            node("n6", "resolution", "Lease time corrected", k=[k2], e=[e4]),
            node("n7", "escalation", "Escalate to the network operations lead"),
        ],
        [
            edge("n1", "n2", "Continue"),
            edge("n2", "n3", "No"),
            edge("n2", "n4", "Yes, did not help"),
            edge("n3", "n5", "Worked"),
            edge("n3", "n4", "Did not help"),
            edge("n4", "n6", "Yes"),
            edge("n4", "n7", "No"),
        ],
        conflicts=["Restarting the relay fixed Site 42 but not Site 17."],
        uncertainties=["Router models are not known."],
    )
