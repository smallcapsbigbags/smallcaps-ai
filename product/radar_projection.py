from __future__ import annotations

import re
from collections import defaultdict

from analyst.company_memory import CompanyMemorySnapshot
from analyst.models import AnnouncementInput, AnalystNote
from product.radar import (
    CompanyState,
    ContractTerms,
    ManagementDelivery,
    RadarMetricPoint,
    RadarMetricSeries,
    RadarObservation,
    SurpriseEvent,
)

_DRIVER_TO_STATE = {
    "earnings": "earnings",
    "cash": "cash",
    "balance-sheet": "balance_sheet",
    "dilution": "dilution",
    "operations": "execution",
    "governance": "execution",
    "outlook": "earnings",
}
_DIRECTION_TO_TREND = {
    "favourable": "improving",
    "adverse": "deteriorating",
    "neutral": "stable",
    "mixed": "unknown",
    "unclear": "unknown",
}
_FUNDING_TERMS = ("funding", "liquidity", "covenant", "going concern", "cash runway", "refinanc")
_GROWTH_TERMS = ("revenue", "growth", "order book", "arr", "production", "volume", "sales")


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normal(value: object) -> str:
    return _clean(value).lower().replace("&", " and ")


def _copy_state(state: CompanyState) -> dict[str, str]:
    return {name: getattr(state, name) for name in CompanyState.model_fields}


def company_state_from_note(
    note: AnalystNote,
    *,
    previous: CompanyState | None = None,
) -> CompanyState:
    """Project validated Analyst 3.3 impact drivers into a persistent state vector.

    Untouched dimensions carry forward. A dimension is changed only by a
    structured driver or explicit guidance event; free-form prose does not
    mutate state.
    """

    prior = previous or CompanyState()
    values = _copy_state(prior)
    strongest: dict[str, tuple[int, str]] = {}

    def apply(field_name: str, significance: int, trend: str) -> None:
        current = strongest.get(field_name)
        if current is None or significance > current[0]:
            strongest[field_name] = (significance, trend)
        elif significance == current[0] and current[1] != trend:
            strongest[field_name] = (significance, "unknown")

    for driver in note.impact_drivers:
        field_name = _DRIVER_TO_STATE.get(driver.dimension)
        trend = _DIRECTION_TO_TREND.get(driver.direction, "unknown")
        if field_name:
            apply(field_name, driver.significance, trend)

        rationale = _normal(driver.rationale)
        if driver.dimension in {"balance-sheet", "cash"} and any(
            term in rationale for term in _FUNDING_TERMS
        ):
            apply("funding", driver.significance, trend)
        if driver.dimension in {"earnings", "operations", "outlook"} and any(
            term in rationale for term in _GROWTH_TERMS
        ):
            apply("growth", driver.significance, trend)

    guidance_statuses = {event.status for event in note.guidance_events}
    if "downgraded" in guidance_statuses:
        apply("earnings", 5, "deteriorating")
    elif "upgraded" in guidance_statuses:
        apply("earnings", 5, "improving")
    elif guidance_statuses & {"maintained", "reiterated"} and values["earnings"] == "unknown":
        apply("earnings", 2, "stable")

    for field_name, (_significance, trend) in strongest.items():
        values[field_name] = trend
    return CompanyState.model_validate(values)


def surprise_events_from_note(note: AnalystNote) -> list[SurpriseEvent]:
    events: list[SurpriseEvent] = []
    for event in note.guidance_events:
        if event.status not in {"upgraded", "downgraded"}:
            continue
        direction = "positive" if event.status == "upgraded" else "negative"
        events.append(
            SurpriseEvent(
                metric=event.metric,
                expected=event.previous_value or event.comparator,
                actual=event.value,
                direction=direction,
                expectation_source_id=event.previous_source_id,
                actual_source_id=note.source_id,
                note=event.note,
            )
        )
    return events


def metric_series_from_memory(memory: CompanyMemorySnapshot) -> list[RadarMetricSeries]:
    output: list[RadarMetricSeries] = []
    for series in memory.metric_series:
        points = [
            RadarMetricPoint(
                source_id=point.source_id,
                published_at=point.published_at,
                value=point.value,
                value_numeric=point.value_numeric,
            )
            for point in series.points
        ]
        if not points:
            continue
        output.append(
            RadarMetricSeries(
                metric=series.metric,
                period_family=series.period_family,
                unit=series.unit,
                currency=series.currency,
                points=points,
            )
        )
    return output


def management_delivery_from_memory(memory: CompanyMemorySnapshot) -> ManagementDelivery | None:
    claims = [*memory.open_management_claims, *memory.resolved_management_claims]
    if not claims:
        return None
    counts: dict[str, int] = defaultdict(int)
    for claim in claims:
        counts[_normal(claim.status)] += 1
    return ManagementDelivery(
        delivered=counts["delivered"],
        delayed=counts["superseded"],
        missed=counts["missed"],
        open=counts["open"],
    )


def _fact_numeric(fact) -> float | None:
    if fact.value_numeric is not None:
        return float(fact.value_numeric)
    text = _clean(fact.value).replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def contract_terms_from_note(note: AnalystNote) -> ContractTerms | None:
    if _normal(note.rns_type) not in {"contracts", "contract", "partnerships"}:
        return None

    headline: float | None = None
    committed: float | None = None
    optional: float | None = None
    currency = "GBP"
    margin_disclosed = False

    for fact in note.key_facts:
        label = _normal(f"{fact.label} {fact.metric}")
        if "margin" in label and fact.basis != "not-disclosed":
            margin_disclosed = True
        numeric = _fact_numeric(fact)
        if numeric is None:
            continue
        if fact.currency:
            currency = fact.currency
        if any(term in label for term in ("committed", "firm value", "minimum value")):
            committed = numeric
        elif any(term in label for term in ("optional", "option value", "extension value")):
            optional = numeric
        elif any(term in label for term in ("headline value", "total contract", "contract value", "potential value")):
            headline = numeric

    if committed is None:
        return None
    if headline is None and optional is not None:
        headline = committed + optional
    if headline is None:
        return None
    if optional is None and headline > committed:
        optional = headline - committed
    return ContractTerms(
        headline_value=headline,
        committed_value=committed,
        optional_value=optional,
        currency=currency,
        margin_disclosed=margin_disclosed,
    )


def outlook_from_note(note: AnalystNote) -> str:
    statuses = {event.status for event in note.guidance_events}
    if "downgraded" in statuses and "upgraded" in statuses:
        return "MIXED"
    if "downgraded" in statuses:
        return "DOWNGRADED"
    if "upgraded" in statuses:
        return "UPGRADED"
    if statuses & {"issued"}:
        return "NEW GUIDANCE"
    if statuses & {"maintained", "reiterated"}:
        return "MAINTAINED"
    return "N/A"


def build_radar_observation(
    *,
    announcement: AnnouncementInput,
    note: AnalystNote,
    memory: CompanyMemorySnapshot,
    previous_state: CompanyState | None = None,
) -> RadarObservation:
    prior = previous_state or CompanyState()
    current = company_state_from_note(note, previous=prior)
    return RadarObservation(
        source_id=announcement.source_id,
        ticker=announcement.ticker,
        company=announcement.company,
        published_at=announcement.published_at,
        title=announcement.title,
        rns_type=note.rns_type,
        source_url=announcement.source_url,
        impact_score=note.impact_score,
        signal=note.impact_colour.upper() if note.impact_colour != "grey" else "NO COLOUR",
        outlook=outlook_from_note(note),
        what_changed=note.what_changed.read_through,
        analyst_view=note.analyst_view,
        previous_state=prior,
        current_state=current,
        surprises=surprise_events_from_note(note),
        metric_series=metric_series_from_memory(memory),
        contract=contract_terms_from_note(note),
        management_delivery=management_delivery_from_memory(memory),
        disclosure_gaps=list(note.disclosure_assessment.missing_items),
    )
