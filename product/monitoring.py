from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from analyst.monitoring_sheet import MonitoringOutlook, MonitoringSignal

MONITORING_SCHEMA_VERSION = "scbb-monitoring-v1"
MonitoringSort = Literal["latest", "impact"]
BalanceSheetStatus = Literal["current", "carried", "not-disclosed"]
MarketReactionStatus = Literal["available", "pending"]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\b[\w£$€%.-]+\b")


class MonitoringModel(BaseModel):
    """Strict public model so API drift fails in tests rather than in the frontend."""

    model_config = ConfigDict(extra="forbid")


class MonitoringImpact(MonitoringModel):
    score: int = Field(ge=1, le=5)
    level: Literal["low", "medium", "high", "critical"]


class MonitoringMarketReaction(MonitoringModel):
    status: MarketReactionStatus
    label: str
    phase: str = "pending"
    reaction_session: str = ""
    change_pct: float | None = None
    previous_close: float | None = None
    open_price: float | None = None
    latest_price: float | None = None
    close_price: float | None = None
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    currency: str = "GBp"
    source: str = ""
    observed_at: str = ""


class MonitoringBalanceSheet(MonitoringModel):
    status: BalanceSheetStatus
    label: str
    value: str
    metric: str = ""
    period: str = ""
    as_of_date: str = ""
    basis: str = ""
    information_status: str = ""
    note: str = ""
    source_id: str = ""
    source_published_at: str = ""


class MonitoringFact(MonitoringModel):
    ordinal: int = 0
    label: str
    value: str
    basis: str
    metric: str = ""
    period: str = ""
    unit: str = ""
    currency: str = ""
    as_of_date: str = ""
    value_numeric: float | None = None
    value_low: float | None = None
    value_high: float | None = None
    note: str = ""
    comparator: str = ""
    comparator_type: str = "none"
    comparator_source_id: str = ""
    previous_value: str = ""
    information_status: str = "new"


class MonitoringGuidanceEvent(MonitoringModel):
    ordinal: int = 0
    metric: str
    period: str = ""
    value: str = ""
    status: str
    comparator: str = ""
    previous_value: str = ""
    previous_source_id: str = ""
    information_status: str = "new"
    note: str = ""


class MonitoringManagementClaim(MonitoringModel):
    ordinal: int = 0
    claim: str
    claim_key: str = ""
    metric: str = ""
    target_value: str = ""
    target_date: str = ""
    status: str = "open"
    outcome: str = ""
    evidence: str = ""


class MonitoringWhatChanged(MonitoringModel):
    before: str
    today: str
    read_through: str
    coverage_status: Literal["building", "established"] = "building"


class MonitoringConceptExplanation(MonitoringModel):
    term: str
    plain_english: str
    why_it_matters: str


class MonitoringDisclosure(MonitoringModel):
    status: Literal["complete", "partial", "insufficient"] = "partial"
    missing_items: list[str] = Field(default_factory=list)
    management_language_mismatch: str = ""
    note: str = ""
    concept_explanations: list[MonitoringConceptExplanation] = Field(
        default_factory=list
    )


class MonitoringProvenance(MonitoringModel):
    evidence_status: str
    quality_status: str
    confidence: float = Field(ge=0.0, le=1.0)
    analysis_version: str
    prompt_version: str
    model_version: str
    source_note: str = ""
    source_warnings: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    ai_view_compacted: bool = False


class MonitoringResearch(MonitoringModel):
    verdict: str
    takeaway: str
    what_changed: MonitoringWhatChanged
    evidence: list[MonitoringFact] = Field(default_factory=list)
    analyst_view: str
    supports_case: list[str] = Field(default_factory=list)
    challenges_case: list[str] = Field(default_factory=list)
    guidance_events: list[MonitoringGuidanceEvent] = Field(default_factory=list)
    management_claims: list[MonitoringManagementClaim] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)
    disclosure: MonitoringDisclosure
    provenance: MonitoringProvenance


class MonitoringSheetRow(MonitoringModel):
    schema_version: Literal["scbb-monitoring-v1"] = MONITORING_SCHEMA_VERSION
    source_id: str
    ticker: str
    company: str
    market: str = "AIM"
    isin: str = ""
    published_at: datetime
    rns_title: str
    rns_type: str
    signal: MonitoringSignal
    takeaway: str = ""
    what_changed: str
    ai_view: str
    outlook: MonitoringOutlook
    market_reaction: MonitoringMarketReaction
    balance_sheet: MonitoringBalanceSheet
    impact: MonitoringImpact
    detail_url: str
    original_source_url: str


class MonitoringSheetDetail(MonitoringSheetRow):
    research: MonitoringResearch


class MonitoringQueryEcho(MonitoringModel):
    date_from: str
    date_to: str
    tickers: list[str] = Field(default_factory=list)
    search: str = ""
    signals: list[MonitoringSignal] = Field(default_factory=list)
    outlooks: list[MonitoringOutlook] = Field(default_factory=list)
    sort: MonitoringSort = "latest"
    limit: int = Field(ge=1, le=250)
    offset: int = Field(ge=0)


class MonitoringSheetPage(MonitoringModel):
    schema_version: Literal["scbb-monitoring-v1"] = MONITORING_SCHEMA_VERSION
    generated_at: datetime
    query: MonitoringQueryEcho
    total: int = Field(ge=0)
    count: int = Field(ge=0)
    has_more: bool
    items: list[MonitoringSheetRow] = Field(default_factory=list)


def clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def compact_ai_view(text: object, *, max_words: int = 50) -> tuple[str, bool]:
    """Return a monitoring-sheet AI View without inventing or paraphrasing content.

    Analyst 3.3 output already complies with the 50-word contract. This adapter exists
    only for older publishable analyses: it keeps complete leading sentences where
    possible and otherwise clips at a word boundary.
    """

    clean = clean_text(text)
    if not clean or word_count(clean) <= max_words:
        return clean, False

    chosen: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(clean):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = " ".join([*chosen, sentence])
        if word_count(candidate) > max_words:
            break
        chosen.append(sentence)

    if chosen:
        return " ".join(chosen), True

    words = clean.split()
    clipped = " ".join(words[:max_words]).rstrip(" ,;:-")
    return clipped + "…", True


def market_reaction_from_price(
    price: dict[str, Any] | None,
) -> MonitoringMarketReaction:
    if not price or price.get("daily_change_pct") is None:
        return MonitoringMarketReaction(status="pending", label="Pending")

    change = float(price["daily_change_pct"])
    phase = clean_text(price.get("phase") or "intraday")
    label = f"{change:+.1f}% at close" if phase == "close" else f"{change:+.1f}% today"
    return MonitoringMarketReaction(
        status="available",
        label=label,
        phase=phase,
        reaction_session=clean_text(price.get("reaction_session")),
        change_pct=change,
        previous_close=_optional_float(price.get("previous_close")),
        open_price=_optional_float(price.get("open_price")),
        latest_price=_optional_float(price.get("latest_price")),
        close_price=_optional_float(price.get("close_price")),
        return_1d=_optional_float(price.get("return_1d")),
        return_5d=_optional_float(price.get("return_5d")),
        return_20d=_optional_float(price.get("return_20d")),
        currency=clean_text(price.get("currency")) or "GBp",
        source=clean_text(price.get("source")),
        observed_at=clean_text(price.get("observed_at")),
    )


def balance_sheet_from_fact(
    fact: dict[str, Any] | None,
    *,
    status: BalanceSheetStatus,
    source_id: str = "",
    source_published_at: str = "",
) -> MonitoringBalanceSheet:
    if not fact:
        return MonitoringBalanceSheet(
            status="not-disclosed",
            label="Balance sheet",
            value="Not disclosed",
        )

    return MonitoringBalanceSheet(
        status=status,
        label=clean_text(fact.get("label") or fact.get("metric") or "Balance sheet"),
        value=clean_text(fact.get("value")) or "Not disclosed",
        metric=clean_text(fact.get("metric")),
        period=clean_text(fact.get("period")),
        as_of_date=clean_text(fact.get("as_of_date")),
        basis=clean_text(fact.get("basis")),
        information_status=clean_text(fact.get("information_status")),
        note=clean_text(fact.get("note")),
        source_id=source_id,
        source_published_at=source_published_at,
    )


def monitoring_fact(data: dict[str, Any]) -> MonitoringFact:
    return MonitoringFact(
        ordinal=int(data.get("ordinal") or 0),
        label=clean_text(data.get("label") or data.get("metric") or "Reported fact"),
        value=clean_text(data.get("value")),
        basis=clean_text(data.get("basis")) or "reported",
        metric=clean_text(data.get("metric")),
        period=clean_text(data.get("period")),
        unit=clean_text(data.get("unit")),
        currency=clean_text(data.get("currency")),
        as_of_date=clean_text(data.get("as_of_date")),
        value_numeric=_optional_float(data.get("value_numeric")),
        value_low=_optional_float(data.get("value_low")),
        value_high=_optional_float(data.get("value_high")),
        note=clean_text(data.get("note")),
        comparator=clean_text(data.get("comparator")),
        comparator_type=clean_text(data.get("comparator_type")) or "none",
        comparator_source_id=clean_text(data.get("comparator_source_id")),
        previous_value=clean_text(data.get("previous_value")),
        information_status=clean_text(data.get("information_status")) or "new",
    )


def monitoring_guidance(data: dict[str, Any]) -> MonitoringGuidanceEvent:
    return MonitoringGuidanceEvent(
        ordinal=int(data.get("ordinal") or 0),
        metric=clean_text(data.get("metric")) or "Guidance",
        period=clean_text(data.get("period")),
        value=clean_text(data.get("value")),
        status=clean_text(data.get("status")) or "not-disclosed",
        comparator=clean_text(data.get("comparator")),
        previous_value=clean_text(data.get("previous_value")),
        previous_source_id=clean_text(data.get("previous_source_id")),
        information_status=clean_text(data.get("information_status")) or "new",
        note=clean_text(data.get("note")),
    )


def monitoring_claim(data: dict[str, Any]) -> MonitoringManagementClaim:
    return MonitoringManagementClaim(
        ordinal=int(data.get("ordinal") or 0),
        claim=clean_text(data.get("claim")),
        claim_key=clean_text(data.get("claim_key")),
        metric=clean_text(data.get("metric")),
        target_value=clean_text(data.get("target_value")),
        target_date=clean_text(data.get("target_date")),
        status=clean_text(data.get("status")) or "open",
        outcome=clean_text(data.get("outcome")),
        evidence=clean_text(data.get("evidence")),
    )


def monitoring_disclosure(data: dict[str, Any] | None) -> MonitoringDisclosure:
    payload = dict(data or {})
    explanations = []
    for item in list(payload.get("concept_explanations") or []):
        if not isinstance(item, dict):
            continue
        term = clean_text(item.get("term"))
        plain = clean_text(item.get("plain_english"))
        why = clean_text(item.get("why_it_matters"))
        if term and plain and why:
            explanations.append(
                MonitoringConceptExplanation(
                    term=term,
                    plain_english=plain,
                    why_it_matters=why,
                )
            )
    status = clean_text(payload.get("status"))
    if status not in {"complete", "partial", "insufficient"}:
        status = "partial"
    return MonitoringDisclosure(
        status=status,  # type: ignore[arg-type]
        missing_items=[clean_text(item) for item in payload.get("missing_items") or [] if clean_text(item)],
        management_language_mismatch=clean_text(
            payload.get("management_language_mismatch")
        ),
        note=clean_text(payload.get("note")),
        concept_explanations=explanations,
    )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
