"""Structured output Gemini must return for one conversation thread.

Messages are referenced by short labels ("M1", "M2", ...) assigned per request.
The server maps labels back to real message IDs and rejects any label that was
not part of the analyzed thread, so the model cannot invent evidence.
"""

from typing import Literal

from pydantic import BaseModel, Field

Classification = Literal[
    "irrelevant",
    "incident_without_resolution",
    "unverified_suggestion",
    "confirmed_resolution",
    "workaround_or_exception",
    "contradictory_or_incomplete",
    "access_information",
]

ActionOutcome = Literal[
    "successful", "unsuccessful", "partially_successful", "not_attempted", "unknown"
]

EvidenceRole = Literal[
    "problem_report",
    "attempted_fix",
    "suggested_solution",
    "confirmed_resolution",
    "applicability_condition",
]

ResolutionStatusValue = Literal["unknown", "suggested", "confirmed_in_conversation"]


class ExtractedAction(BaseModel):
    action: str = Field(description="What was done or proposed, in plain words.")
    outcome: ActionOutcome = Field(
        description=(
            "successful/unsuccessful/partially_successful only if a message states the result; "
            "not_attempted for proposals nobody tried; unknown otherwise."
        )
    )
    message_refs: list[str] = Field(description="Labels (e.g. M2) of messages describing it.")


class ExtractedEvidence(BaseModel):
    message_ref: str = Field(description="Label of one message, e.g. M3.")
    evidence_type: EvidenceRole
    explanation: str = Field(description="One short sentence: why this message supports it.")


class ThreadAnalysis(BaseModel):
    classification: Classification
    knowledge_type: Literal["troubleshooting", "site_access"] = Field(
        default="troubleshooting",
        description="site_access for how to physically reach a site (keys, barriers, gates, roads, "
                    "contacts); troubleshooting otherwise."
    )
    is_valuable_knowledge: bool = Field(
        description="True only if another engineer could reuse this to troubleshoot later."
    )
    title: str | None = Field(description="Short title of the knowledge, or null.")
    problem_description: str | None
    symptoms: list[str]
    root_cause: str | None = Field(description="Only if stated in the conversation, else null.")
    equipment_identifiers: list[str] = Field(
        description="Device/site/service identifiers copied exactly as written. Never invent."
    )
    site_identifiers: list[str] = Field(
        default_factory=list,
        description="Site identifiers copied exactly as written (e.g. SITE-PELLO-03). Never invent."
    )
    scope: Literal["this_equipment_only", "same_equipment_class", "unknown"] = Field(
        default="unknown",
        description=(
            "same_equipment_class only if a message says it applies to that type/family/generation of "
            "units (e.g. 'these older units'); this_equipment_only if it is specific to the device; "
            "unknown otherwise."
        )
    )
    scope_description: str | None = Field(
        default=None,
        description="The unit class as described in the conversation (e.g. 'older transmission units, "
                    "installed around 2019'), or null."
    )
    trigger_events: list[str] = Field(
        default_factory=list,
        description="Operational events the knowledge is about, in a few words (e.g. 'SFP replacement'). "
                    "Only events mentioned in the conversation."
    )
    incident_numbers: list[str] = Field(
        description="Incident/ticket numbers copied exactly as written. Usually empty."
    )
    attempted_actions: list[ExtractedAction]
    resolution: str | None = Field(description="The fix or recommended action, or null.")
    resolution_status: ResolutionStatusValue = Field(
        description=(
            "confirmed_in_conversation only if a message explicitly reports the fix worked; "
            "suggested if a fix was proposed but not confirmed; unknown otherwise."
        )
    )
    applicability_conditions: list[str] = Field(
        description="When the fix applies or must not be used (warnings, exceptions)."
    )
    missing_information: list[str] = Field(
        description="Details an engineer would need that the conversation does not give."
    )
    evidence: list[ExtractedEvidence]
    confidence: float = Field(ge=0, le=1, description="Confidence in this analysis, 0 to 1.")
    rationale: str = Field(description="One or two sentences explaining the classification.")
