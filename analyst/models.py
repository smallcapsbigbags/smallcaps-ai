from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ImpactColour = Literal["green", "amber", "red", "grey"]
ImpactLevel = Literal["low", "medium", "high", "critical"]
FactBasis = Literal["reported", "calculated", "not-disclosed", "source-warning"]
InformationStatus = Literal[
    "new", "reiterated", "previously-disclosed", "not-disclosed"
]
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
EvidenceStatus = Literal["complete", "partial", "unavailable", "metadata-only"]
ComparatorType = Literal[
    "prior-guidance",
    "prior-period",
    "prior-disclosure",
    "transaction-stage",
    "verified-denominator",
    "none",
]
ImpactDimension = Literal[
    "earnings",
    "cash",
    "balance-sheet",
    "dilution",
    "operations",
    "outlook",
    "governance",
    "ownership",
    "transaction",
    "other",
]
DriverDirection = Literal["favourable", "adverse", "mixed", "neutral", "unclear"]
DisclosureStatus = Literal["complete", "partial", "insufficient"]
QualitySeverity = Literal["info", "review", "block"]
QualityStatus = Literal["publishable", "review", "blocked"]


class StrictModel(BaseModel):
    """Reject undeclared model output so schema drift fails loudly."""

    model_config = ConfigDict(extra="forbid")


def impact_level_from_score(score: int) -> ImpactLevel:
    """Map the internal 1–5 score to restrained public language."""

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
    source_urls: list[str] = Field(default_factory=list)
    source_note: str = ""
    evidence_status: EvidenceStatus = "complete"
    evidence_retrieved_at: datetime | None = None
    rns_type: str = "Other"
    categories: list[str] = Field(default_factory=list)
    isin: str = ""

    @field_validator("source_id", "company", "title", "text")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, value: str) -> str:
        cleaned = value.upper().strip().replace(".L", "").rstrip(".-")
        if not cleaned:
            raise ValueError("ticker must not be blank")
        return cleaned

    @model_validator(mode="after")
    def require_timezone(self) -> "AnnouncementInput":
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if (
            self.evidence_retrieved_at is not None
            and self.evidence_retrieved_at.tzinfo is None
        ):
            raise ValueError("evidence_retrieved_at must be timezone-aware")
        return self


class KeyFact(StrictModel):
    label: str
    value: str
    basis: FactBasis
    note: str = ""
    metric: str = ""
    period: str = ""
    unit: str = ""
    currency: str = ""
    as_of_date: str = ""
    value_numeric: float | None = None
    value_low: float | None = None
    value_high: float | None = None
    comparator: str = ""
    comparator_type: ComparatorType = "none"
    comparator_source_id: str = ""
    previous_value: str = ""
    information_status: InformationStatus = "new"

    @model_validator(mode="after")
    def validate_fact_semantics(self) -> "KeyFact":
        if self.basis == "calculated" and not self.note.strip():
            raise ValueError("calculated facts must show their disclosed inputs in note")
        if self.basis == "not-disclosed" and self.value.strip().lower() != "not disclosed":
            raise ValueError("not-disclosed facts must use value 'Not disclosed'")
        if (
            self.value_low is not None
            and self.value_high is not None
            and self.value_low > self.value_high
        ):
            raise ValueError("value_low cannot exceed value_high")
        return self


class GuidanceEvent(StrictModel):
    metric: str
    period: str = ""
    value: str = ""
    status: GuidanceStatus
    comparator: str = ""
    previous_value: str = ""
    previous_source_id: str = ""
    information_status: InformationStatus = "new"
    note: str = ""


class ManagementClaim(StrictModel):
    claim: str
    claim_key: str = ""
    metric: str = ""
    target_value: str = ""
    target_date: str = ""
    status: ClaimStatus = "open"
    outcome: str = ""
    evidence: str = ""


class WhatChanged(StrictModel):
    before: str
    today: str
    read_through: str
    coverage_status: Literal["building", "established"] = "building"


class ImpactDriver(StrictModel):
    dimension: ImpactDimension
    direction: DriverDirection
    significance: int = Field(ge=1, le=5)
    rationale: str


class DisclosureAssessment(StrictModel):
    status: DisclosureStatus = "partial"
    missing_items: list[str] = Field(default_factory=list)
    management_language_mismatch: str = ""
    note: str = ""


class QualityFlag(StrictModel):
    code: str
    severity: QualitySeverity
    message: str


class QualityReport(StrictModel):
    status: QualityStatus
    flags: list[QualityFlag] = Field(default_factory=list)

    @property
    def publishable(self) -> bool:
        return self.status == "publishable"


class AnalystNote(StrictModel):
    source_id: str
    rns_type: str
    impact_colour: ImpactColour
    impact_score: int = Field(ge=1, le=5)
    impact_level: ImpactLevel
    impact_rationale: str = ""
    impact_drivers: list[ImpactDriver] = Field(default_factory=list)
    headline: str = Field(min_length=4, max_length=180)
    takeaway: str
    key_facts: list[KeyFact] = Field(default_factory=list)
    new_information: list[str] = Field(default_factory=list)
    reiterated_information: list[str] = Field(default_factory=list)
    what_changed: WhatChanged
    analyst_view: str
    supports_case: list[str] = Field(default_factory=list)
    challenges_case: list[str] = Field(default_factory=list)
    guidance_events: list[GuidanceEvent] = Field(default_factory=list)
    management_claims: list[ManagementClaim] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)
    disclosure_assessment: DisclosureAssessment = Field(
        default_factory=DisclosureAssessment
    )
    source_references: list[str] = Field(default_factory=list)
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
    quality_status: QualityStatus = "publishable"
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    created_at: datetime
