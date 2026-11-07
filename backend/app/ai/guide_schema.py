"""Structured output Gemini returns when drafting a troubleshooting decision tree.

Knowledge and evidence are referenced by per-request labels (K1, E3, ...). The server maps
them back to real IDs and rejects anything that was not part of the retrieved context.
"""

from typing import Literal

from pydantic import BaseModel, Field

NodeType = Literal["start", "question", "diagnostic", "recommendation", "resolution", "escalation"]


class DraftNode(BaseModel):
    id: str = Field(description="Short unique id, e.g. n1.")
    node_type: NodeType
    title: str = Field(description="Short step title.")
    description: str | None = Field(description="What to check or why, based only on the evidence.")
    question: str | None = Field(description="Question for the engineer (question/diagnostic nodes).")
    applicability_conditions: list[str] = Field(
        description="When this step applies or must not be used, copied from the knowledge."
    )
    knowledge_refs: list[str] = Field(description="Labels of knowledge items this step is based on, e.g. K1.")
    evidence_refs: list[str] = Field(description="Labels of supporting messages, e.g. E2.")
    conflict_note: str | None = Field(
        description="If sources disagree about this step, explain the disagreement; else null."
    )


class DraftEdge(BaseModel):
    source: str = Field(description="id of the node the answer belongs to.")
    target: str = Field(description="id of the next node.")
    answer_label: str = Field(description="Answer that leads here, e.g. Yes, No, Continue, Did not help.")
    condition: str | None = Field(description="Optional extra condition for this branch.")


class GuideDraft(BaseModel):
    sufficient_evidence: bool = Field(
        description="False if the retrieved knowledge does not address this problem."
    )
    insufficiency_reason: str | None
    title: str
    summary: str = Field(description="One or two sentences describing the guide.")
    nodes: list[DraftNode]
    edges: list[DraftEdge]
    conflicts: list[str] = Field(description="Disagreements between sources, in plain words.")
    uncertainties: list[str] = Field(description="Missing information or unclear applicability.")
