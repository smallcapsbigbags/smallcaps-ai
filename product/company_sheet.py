from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from analyst.monitoring_sheet import MonitoringSignal
from product.monitoring import (
    MonitoringImpact,
    MonitoringMarketReaction,
    MonitoringSheetDetail,
)

COMPANY_SHEET_SCHEMA_VERSION = "scbb-company-v1"


class CompanySheetModel(BaseModel):
    """Strict public model so Company Intelligence cannot drift under the frontend."""

    model_config = ConfigDict(extra="forbid")


class CompanyCoverage(CompanySheetModel):
    status: Literal["building", "established"] = "building"
    coverage_since: str = ""
    latest_covered_at: str = ""
    coverage_days: int = Field(default=0, ge=0)
    announcement_count: int = Field(default=0, ge=0)


class CompanyGuidanceItem(CompanySheetModel):
    key: str = ""
    source_id: str
    published_at: str
    title: str
    source_url: str = ""
    metric: str
    period: str = ""
    value: str = ""
    status: str
    comparator: str = ""
    previous_value: str = ""
    note: str = ""


class CompanyMetricPoint(CompanySheetModel):
    source_id: str
    published_at: str
    title: str
    source_url: str = ""
    label: str
    metric: str
    period: str = ""
    value: str
    value_numeric: float | None = None
    value_low: float | None = None
    value_high: float | None = None
    unit: str = ""
    currency: str = ""
    as_of_date: str = ""
    basis: str = "reported"
    note: str = ""


class CompanyMetricSeries(CompanySheetModel):
    key: str
    metric: str
    label: str
    period_family: str
    basis: str = "reported"
    unit: str = ""
    currency: str = ""
    latest_value: str
    previous_value: str = ""
    change_direction: Literal["up", "down", "flat", "unclear"] = "unclear"
    change_absolute: float | None = None
    change_percent: float | None = None
    points: list[CompanyMetricPoint] = Field(default_factory=list)


class CompanyClaim(CompanySheetModel):
    key: str = ""
    source_id: str
    published_at: str
    title: str
    source_url: str = ""
    claim: str
    metric: str = ""
    target_value: str = ""
    target_date: str = ""
    status: str = "open"
    outcome: str = ""
    evidence: str = ""


class CompanyDisclosureGap(CompanySheetModel):
    item: str
    source_id: str
    published_at: str
    title: str
    source_url: str = ""


class CompanyTimelineItem(CompanySheetModel):
    source_id: str
    published_at: datetime
    rns_type: str = ""
    signal: MonitoringSignal
    headline: str
    takeaway: str = ""
    market_reaction: MonitoringMarketReaction
    impact: MonitoringImpact
    detail_url: str
    original_source_url: str = ""


class CompanySheet(CompanySheetModel):
    schema_version: Literal["scbb-company-v1"] = COMPANY_SHEET_SCHEMA_VERSION
    generated_at: datetime
    ticker: str
    company: str
    market: str = "AIM"
    isin: str = ""
    coverage: CompanyCoverage
    current_position: MonitoringSheetDetail | None = None
    guidance: list[CompanyGuidanceItem] = Field(default_factory=list)
    metrics: list[CompanyMetricSeries] = Field(default_factory=list)
    open_management_claims: list[CompanyClaim] = Field(default_factory=list)
    resolved_management_claims: list[CompanyClaim] = Field(default_factory=list)
    disclosure_gaps: list[CompanyDisclosureGap] = Field(default_factory=list)
    history: list[CompanyTimelineItem] = Field(default_factory=list)
    has_more_history: bool = False

    @model_validator(mode="after")
    def prefer_dated_carried_balance_context(self) -> "CompanySheet":
        """Avoid presenting a generic accounting period as a disclosure date.

        Some historic facts use ``Point in time`` as their period family.  On the
        company page a carried balance-sheet figure is clearer when it falls back
        to the source RNS publication date instead of displaying that generic label.
        The underlying monitoring record and fact provenance remain unchanged.
        """

        current = self.current_position
        if current is None:
            return self
        balance = current.balance_sheet
        generic_periods = {"point in time", "instant", "as at"}
        if (
            balance.status == "carried"
            and not balance.as_of_date.strip()
            and balance.period.strip().lower() in generic_periods
            and balance.source_published_at.strip()
        ):
            balance.period = ""
        return self
