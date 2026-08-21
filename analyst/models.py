from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ImpactColour = Literal["green", "amber", "red", "grey"]
ImpactLevel = Literal["low", "medium", "high", "critical"]
FactBasis = Literal["reported", "calculated", "not-disclosed", "source-warning"]
InformationStatus = Literal["new", "reiterated", "previously-disclosed", "not-disclosed"]
GuidanceStatus = Literal[
    "issued",
    "reiterated",
    "upgraded",
    "downgraded",
    "maintained",
    "withdrawn",
    "delivered",
    "missed",
    "not-applicable",
    "not-disclosed",
]
ClaimStatus = Literal["open", "delivered", "missed", "superseded", "not-assessable"]


class StrictModel(BaseModel):
    """Reject undeclared model output so schema drift fails loudly."""

    model_config = ConfigDict(extra="forbid")


def impact_level_from_score(score: int) -> ImpactLevel:
    """Map the internal 1–5 score to the restrained public language."""

    if score == 1:
        return "low"
    if score == 2:
        return "medium"
    if score in {3, 4}:
        return "high"
    return "critical"


class AnnouncementInput(StrictModel):
    source_id: str
    ticker: str
    company: str
    published_at: datetime
    title: str
    text: str
    source_url: str = ""
    rns_type: str = "Other"
    categories: list[str] = Field(default_factory=list)
    isin: str = ""


class KeyFact(StrictModel):
    label: str
    value: str
    basis: FactBasis
    note: str = ""
    metric: str = ""
    period: str = ""
    unit: str = ""
    comparator: str = ""
    previous_value: str = ""
    information_status: InformationStatus = "new"


class GuidanceEvent(StrictModel):
    metric: str
    period: str = ""
    value: str = ""
    status: GuidanceStatus
    comparator: str = ""
    note: str = ""


class ManagementClaim(StrictModel):
    claim: str
    target_date: str = ""
    status: ClaimStatus = "open"
    outcome: str = ""
    evidence: str = ""


class WhatChanged(StrictModel):
    before: str
    today: str
    read_through: str
    coverage_status: Literal["building", "established"] = "building"


class AnalystNote(StrictModel):
    source_id: str
    rns_type: str
    impact_colour: ImpactColour
    impact_score: int = Field(ge=1, le=5)
    impact_level: ImpactLevel
    headline: str
    takeaway: str
    key_facts: list[KeyFact] = Field(default_factory=list)
    what_changed: WhatChanged
    analyst_view: str
    supports_case: list[str] = Field(default_factory=list)
    challenges_case: list[str] = Field(default_factory=list)
    guidance_events: list[GuidanceEvent] = Field(default_factory=list)
    management_claims: list[ManagementClaim] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)
    source_warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

    @model_validator(mode="after")
    def validate_impact_level(self) -> "AnalystNote":
        expected = impact_level_from_score(self.impact_score)
        if self.impact_level != expected:
            raise ValueError(
                f"impact_level must be '{expected}' when impact_score is {self.impact_score}"
            )
        return self


class PersistedAnalysis(StrictModel):
    company_id: str
    announcement_id: str
    analyst_run_id: str
    source_id: str
    impact_colour: ImpactColour
    impact_level: ImpactLevel
    created_at: datetime
