from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from analyst.models import StrictModel

RADAR_SCHEMA_VERSION = "aim-radar-v1"
RADAR_VERSION = "aim-radar-1.0"

StateTrend = Literal["improving", "stable", "deteriorating", "unknown"]
RadarSetupType = Literal[
    "QUIET_IMPROVEMENT",
    "HIDDEN_DETERIORATION",
    "OVERREACTION",
    "UNDERREACTION",
    "READ_THE_SMALL_PRINT",
    "MANAGEMENT_DELIVERING",
    "FUNDING_CLOCK",
    "EARNINGS_INFLECTION",
    "DELEVERAGING",
]
RadarStatus = Literal["new", "active", "resolved", "invalidated"]
RadarConfidence = Literal["low", "medium", "high"]


class CompanyState(StrictModel):
    earnings: StateTrend = "unknown"
    growth: StateTrend = "unknown"
    cash: StateTrend = "unknown"
    balance_sheet: StateTrend = "unknown"
    execution: StateTrend = "unknown"
    funding: StateTrend = "unknown"
    dilution: StateTrend = "unknown"

    def changed_dimensions(self, previous: "CompanyState") -> list[str]:
        output: list[str] = []
        for field_name in self.model_fields:
            current = getattr(self, field_name)
            prior = getattr(previous, field_name)
            if current != prior:
                output.append(field_name)
        return output


class SurpriseEvent(StrictModel):
    metric: str
    expected: str = ""
    actual: str = ""
    expected_numeric: float | None = None
    actual_numeric: float | None = None
    delta: float | None = None
    delta_percent: float | None = None
    direction: Literal["positive", "negative", "neutral", "unclear"] = "unclear"
    expectation_source_id: str = ""
    actual_source_id: str = ""
    note: str = ""


class RadarMetricPoint(StrictModel):
    source_id: str
    published_at: str
    value: str
    value_numeric: float | None = None


class RadarMetricSeries(StrictModel):
    metric: str
    period_family: str = ""
    unit: str = ""
    currency: str = ""
    points: list[RadarMetricPoint] = Field(default_factory=list)


class ContractTerms(StrictModel):
    headline_value: float | None = None
    committed_value: float | None = None
    optional_value: float | None = None
    currency: str = "GBP"
    margin_disclosed: bool = False


class FundingWindow(StrictModel):
    cash_runway_end: str = ""
    next_major_catalyst: str = ""
    funding_required_before_catalyst: bool | None = None


class ManagementDelivery(StrictModel):
    delivered: int = 0
    delayed: int = 0
    missed: int = 0
    open: int = 0


class RadarObservation(StrictModel):
    source_id: str
    ticker: str
    company: str
    published_at: datetime
    title: str
    rns_type: str = "Other"
    source_url: str = ""
    impact_score: int = Field(default=1, ge=1, le=5)
    signal: str = "NO COLOUR"
    outlook: str = "N/A"
    what_changed: str = ""
    analyst_view: str = ""
    previous_state: CompanyState = Field(default_factory=CompanyState)
    current_state: CompanyState = Field(default_factory=CompanyState)
    surprises: list[SurpriseEvent] = Field(default_factory=list)
    metric_series: list[RadarMetricSeries] = Field(default_factory=list)
    contract: ContractTerms | None = None
    funding_window: FundingWindow | None = None
    management_delivery: ManagementDelivery | None = None
    disclosure_gaps: list[str] = Field(default_factory=list)
    market_reaction_pct: float | None = None


class RadarEvidence(StrictModel):
    source_id: str
    claim: str
    source_url: str = ""


class RadarSetup(StrictModel):
    schema_version: Literal["aim-radar-v1"] = RADAR_SCHEMA_VERSION
    radar_version: Literal["aim-radar-1.0"] = RADAR_VERSION
    ticker: str
    company: str
    setup_type: RadarSetupType
    setup_score: int = Field(ge=0, le=100)
    confidence: RadarConfidence
    status: RadarStatus = "new"
    headline: str
    why_interesting: str
    next_test: str = ""
    primary_source_id: str
    source_ids: list[str] = Field(default_factory=list)
    evidence: list[RadarEvidence] = Field(default_factory=list)
    changed_dimensions: list[str] = Field(default_factory=list)
    reaction_gap: float | None = None
    first_detected_at: datetime | None = None
    last_updated_at: datetime | None = None


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _series(observation: RadarObservation, *names: str) -> RadarMetricSeries | None:
    wanted = {_clean(name).lower() for name in names}
    for series in observation.metric_series:
        metric = _clean(series.metric).lower()
        if metric in wanted or any(name in metric for name in wanted):
            return series
    return None


def _numeric_points(series: RadarMetricSeries | None) -> list[float]:
    if series is None:
        return []
    return [
        float(point.value_numeric)
        for point in series.points
        if point.value_numeric is not None
    ]


def _evidence(observation: RadarObservation, claim: str) -> list[RadarEvidence]:
    return [
        RadarEvidence(
            source_id=observation.source_id,
            source_url=observation.source_url,
            claim=claim,
        )
    ]


def _confidence(score: int, evidence_count: int) -> RadarConfidence:
    if score >= 75 and evidence_count >= 2:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _setup(
    observation: RadarObservation,
    *,
    setup_type: RadarSetupType,
    score: int,
    headline: str,
    why_interesting: str,
    evidence_claims: list[str],
    next_test: str = "",
    reaction_gap: float | None = None,
) -> RadarSetup:
    evidence = [
        RadarEvidence(
            source_id=observation.source_id,
            source_url=observation.source_url,
            claim=claim,
        )
        for claim in evidence_claims
        if _clean(claim)
    ]
    now = observation.published_at
    changed = observation.current_state.changed_dimensions(observation.previous_state)
    return RadarSetup(
        ticker=_clean(observation.ticker).upper(),
        company=_clean(observation.company) or _clean(observation.ticker).upper(),
        setup_type=setup_type,
        setup_score=max(0, min(100, int(score))),
        confidence=_confidence(score, len(evidence)),
        headline=headline,
        why_interesting=why_interesting,
        next_test=next_test,
        primary_source_id=observation.source_id,
        source_ids=[observation.source_id],
        evidence=evidence,
        changed_dimensions=changed,
        reaction_gap=reaction_gap,
        first_detected_at=now,
        last_updated_at=now,
    )


def _detect_read_small_print(observation: RadarObservation) -> RadarSetup | None:
    terms = observation.contract
    if terms is None or terms.headline_value is None or terms.committed_value is None:
        return None
    if terms.headline_value <= 0 or terms.committed_value >= terms.headline_value:
        return None
    committed_ratio = terms.committed_value / terms.headline_value
    if committed_ratio >= 0.75:
        return None
    optional = terms.optional_value
    optional_text = (
        f"; {terms.currency} {optional:g} remains optional"
        if optional is not None and optional > 0
        else ""
    )
    score = 58 + int((1 - committed_ratio) * 30)
    claims = [
        f"Only {committed_ratio:.0%} of the headline contract value is committed{optional_text}.",
    ]
    if not terms.margin_disclosed:
        claims.append("Contract margin is not disclosed.")
    return _setup(
        observation,
        setup_type="READ_THE_SMALL_PRINT",
        score=score,
        headline="The headline value overstates what is actually committed.",
        why_interesting=claims[0],
        evidence_claims=claims,
        next_test="Watch for optional tranches converting into firm revenue and for margin disclosure.",
    )


def _detect_deleveraging(observation: RadarObservation) -> RadarSetup | None:
    series = _series(observation, "net debt")
    points = _numeric_points(series)
    if len(points) < 3:
        return None
    tail = points[-3:]
    if not (tail[0] > tail[1] > tail[2]):
        return None
    reduction = (tail[0] - tail[2]) / abs(tail[0]) if tail[0] else 0.0
    score = 60 + min(25, int(abs(reduction) * 50))
    claim = f"Net debt has fallen across three comparable disclosures: {tail[0]:g} → {tail[1]:g} → {tail[2]:g}."
    return _setup(
        observation,
        setup_type="DELEVERAGING",
        score=score,
        headline="Debt keeps moving the right way.",
        why_interesting=claim,
        evidence_claims=[claim],
        next_test="Check whether lower debt is being driven by repeatable operating cash generation.",
    )


def _detect_hidden_deterioration(observation: RadarObservation) -> RadarSetup | None:
    state = observation.current_state
    prior = observation.previous_state
    newly_bad = [
        name
        for name in state.model_fields
        if getattr(state, name) == "deteriorating"
        and getattr(prior, name) != "deteriorating"
    ]
    severe_negative = [
        item
        for item in observation.surprises
        if item.direction == "negative"
        and item.delta_percent is not None
        and item.delta_percent <= -20
    ]
    balance_or_funding_bad = state.balance_sheet == "deteriorating" or state.funding == "deteriorating"
    if len(newly_bad) < 2 and not (severe_negative and balance_or_funding_bad):
        return None
    score = 62 + min(24, 7 * len(newly_bad) + 5 * len(severe_negative))
    dimensions = ", ".join(name.replace("_", " ") for name in newly_bad) or "balance-sheet/funding risk"
    claim = f"Deterioration is broader than the headline: {dimensions}."
    return _setup(
        observation,
        setup_type="HIDDEN_DETERIORATION",
        score=score,
        headline="The second-order numbers are getting worse.",
        why_interesting=claim,
        evidence_claims=[claim, *[f"{item.metric}: {item.expected or 'expected'} → {item.actual or 'actual'}." for item in severe_negative]],
        next_test="Look for evidence that cash, leverage and execution stabilise at the next update.",
    )


def _detect_earnings_inflection(observation: RadarObservation) -> RadarSetup | None:
    earnings = observation.current_state.earnings
    prior = observation.previous_state.earnings
    positive = [item for item in observation.surprises if item.direction == "positive"]
    outlook = _clean(observation.outlook).upper()
    if earnings != "improving":
        return None
    if prior == "improving" and outlook != "UPGRADED" and not positive:
        return None
    score = 58 + (12 if outlook == "UPGRADED" else 0) + min(15, len(positive) * 5)
    claim = "Earnings moved into an improving state"
    if outlook == "UPGRADED":
        claim += " and guidance was upgraded"
    claim += "."
    return _setup(
        observation,
        setup_type="EARNINGS_INFLECTION",
        score=score,
        headline="Earnings momentum is turning.",
        why_interesting=claim,
        evidence_claims=[claim],
        next_test="Look for the improvement to persist into cash conversion and the next guidance point.",
    )


def _detect_management_delivering(observation: RadarObservation) -> RadarSetup | None:
    delivery = observation.management_delivery
    if delivery is None or delivery.delivered < 2 or delivery.missed > 0:
        return None
    score = 55 + min(25, delivery.delivered * 5) - min(10, delivery.delayed * 2)
    claim = f"Management has delivered {delivery.delivered} tracked commitments with {delivery.missed} misses."
    return _setup(
        observation,
        setup_type="MANAGEMENT_DELIVERING",
        score=score,
        headline="Management keeps doing what it said it would do.",
        why_interesting=claim,
        evidence_claims=[claim],
        next_test="Track whether the next stated milestone is delivered on time and at the promised economics.",
    )


def _parse_date(value: str) -> date | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _detect_funding_clock(observation: RadarObservation) -> RadarSetup | None:
    window = observation.funding_window
    if window is None:
        return None
    runway = _parse_date(window.cash_runway_end)
    catalyst = _parse_date(window.next_major_catalyst)
    if window.funding_required_before_catalyst is not True and not (runway and catalyst and runway < catalyst):
        return None
    score = 74
    if runway and catalyst:
        gap = (catalyst - runway).days
        score += min(15, max(0, gap // 30))
        claim = f"Current cash runway ends about {gap} days before the next major catalyst."
    else:
        claim = "The current evidence indicates funding is required before the next major catalyst."
    return _setup(
        observation,
        setup_type="FUNDING_CLOCK",
        score=score,
        headline="The funding clock is ticking.",
        why_interesting=claim,
        evidence_claims=[claim],
        next_test="Watch for a financing, strategic partner or materially lower cash burn before the catalyst.",
    )


def detect_radar_setups(observation: RadarObservation) -> list[RadarSetup]:
    """Detect evidence-backed, investigation-worthy setups.

    Pass A deliberately excludes market-mismatch detectors (QUIET_IMPROVEMENT,
    UNDERREACTION and OVERREACTION). Those require calibrated price-vs-fundamental
    logic and belong in Radar Pass B.
    """

    detectors = (
        _detect_hidden_deterioration,
        _detect_read_small_print,
        _detect_funding_clock,
        _detect_deleveraging,
        _detect_earnings_inflection,
        _detect_management_delivering,
    )
    setups = [setup for detector in detectors if (setup := detector(observation)) is not None]
    setups.sort(key=lambda item: (item.setup_score, item.setup_type), reverse=True)
    return setups
