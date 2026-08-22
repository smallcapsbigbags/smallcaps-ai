from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from analyst.models import StrictModel

CoverageStatus = Literal["building", "established"]
ChangeDirection = Literal["up", "down", "flat", "unclear"]

_ESTABLISHED_MIN_ANNOUNCEMENTS = 6
_ESTABLISHED_MIN_DAYS = 365
_MAX_GUIDANCE = 10
_MAX_SERIES = 10
_MAX_POINTS_PER_SERIES = 4
_MAX_CLAIMS = 10
_MAX_GAPS = 8
_MAX_GAP_RECORDS = 3
_MAX_IMPACT_HISTORY = 8

_PRIORITY_TERMS: tuple[tuple[str, int], ...] = (
    ("net debt", 30),
    ("net cash", 30),
    ("cash", 24),
    ("liquidity", 24),
    ("covenant", 24),
    ("revenue guidance", 24),
    ("profit guidance", 24),
    ("ebitda guidance", 24),
    ("adjusted ebitda", 22),
    ("ebitda margin", 22),
    ("operating margin", 22),
    ("gross margin", 22),
    ("profit before tax", 21),
    ("operating profit", 21),
    ("free cash flow", 21),
    ("cash conversion", 21),
    ("order book", 20),
    ("arr", 20),
    ("recurring revenue", 20),
    ("net fee income", 20),
    ("loan book", 20),
    ("ltv", 20),
    ("nav", 20),
    ("book value", 20),
    ("completions", 19),
    ("production", 19),
    ("recovery", 19),
    ("aisc", 19),
    ("revenue", 15),
    ("ebitda", 15),
    ("profit", 15),
    ("margin", 15),
    ("debt", 15),
)


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalise(value: object) -> str:
    text = _clean_text(value).lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _clean_text(value)
        if not raw:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: object) -> str:
    parsed = _parse_datetime(value)
    if parsed.year == datetime.min.year:
        return ""
    return parsed.isoformat()


def _metric_priority(metric: str) -> int:
    normalised = _normalise(metric)
    return max(
        (score for term, score in _PRIORITY_TERMS if term in normalised),
        default=0,
    )


def _period_family(period: str, as_of_date: str) -> str:
    """Reduce periods to a safe comparison family.

    Specific sub-periods must be checked before FY because labels such as
    ``H1 FY26`` contain both tokens. H1 and FY are not directly comparable.
    """

    normalised = _normalise(period)
    if re.search(r"\bh1\b", normalised) or "first half" in normalised:
        return "H1"
    if re.search(r"\bh2\b", normalised) or "second half" in normalised:
        return "H2"
    quarter = re.search(r"\bq([1-4])\b", normalised)
    if quarter:
        return f"Q{quarter.group(1)}"
    if "six months" in normalised or "half year" in normalised:
        return "Half year"
    if (
        re.search(r"\bfy\s*\d{2,4}\b", normalised)
        or "full year" in normalised
        or "year ended" in normalised
    ):
        return "FY"
    if as_of_date or not normalised:
        return "Point in time"
    return _clean_text(period)


def _series_key(
    metric: str,
    period: str,
    as_of_date: str,
    unit: str,
    currency: str,
    basis: str,
) -> str:
    # Reported and Smallcaps.ai-calculated figures remain separate series even
    # when their labels happen to match.
    return "|".join(
        (
            _normalise(metric),
            _normalise(_period_family(period, as_of_date)),
            _normalise(unit),
            _normalise(currency),
            _normalise(basis),
        )
    )


def _claim_key(claim: Mapping[str, object]) -> str:
    # An explicit claim_key is a stable database identity. Preserve it exactly
    # rather than normalising punctuation away, so a later RNS can update it.
    explicit = _clean_text(claim.get("claim_key"))
    if explicit:
        return explicit
    fallback = "|".join(
        (
            _normalise(claim.get("metric")),
            _normalise(claim.get("target_date")),
            _normalise(claim.get("claim"))[:100],
        )
    )
    return fallback.strip("|") or _normalise(claim)


def _guidance_key(event: Mapping[str, object]) -> str:
    return "|".join(
        (_normalise(event.get("metric")), _normalise(event.get("period")))
    )


class MemoryMetricPoint(StrictModel):
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


class MemoryMetricSeries(StrictModel):
    key: str
    metric: str
    label: str
    period_family: str
    basis: str = "reported"
    unit: str = ""
    currency: str = ""
    latest_value: str
    previous_value: str = ""
    change_direction: ChangeDirection = "unclear"
    change_absolute: float | None = None
    change_percent: float | None = None
    points: list[MemoryMetricPoint] = Field(default_factory=list)


class MemoryGuidanceItem(StrictModel):
    key: str
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


class MemoryClaimItem(StrictModel):
    key: str
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


class MemoryDisclosureGap(StrictModel):
    item: str
    source_id: str
    published_at: str
    title: str
    source_url: str = ""


class MemoryImpactItem(StrictModel):
    source_id: str
    published_at: str
    title: str
    source_url: str = ""
    rns_type: str = ""
    impact_colour: str
    impact_score: int
    headline: str
    takeaway: str = ""


class CompanyMemorySnapshot(StrictModel):
    context_type: Literal["company_memory_snapshot"] = "company_memory_snapshot"
    ticker: str
    company: str = ""
    generated_before: str = ""
    coverage_status: CoverageStatus = "building"
    coverage_since: str = ""
    latest_covered_at: str = ""
    coverage_days: int = 0
    announcement_count: int = 0
    current_guidance: list[MemoryGuidanceItem] = Field(default_factory=list)
    metric_series: list[MemoryMetricSeries] = Field(default_factory=list)
    open_management_claims: list[MemoryClaimItem] = Field(default_factory=list)
    resolved_management_claims: list[MemoryClaimItem] = Field(default_factory=list)
    disclosure_gaps: list[MemoryDisclosureGap] = Field(default_factory=list)
    recent_impact_history: list[MemoryImpactItem] = Field(default_factory=list)

    def to_context_record(self) -> dict[str, object]:
        """Return a compact, explicit prior-context record for the Analyst Engine."""

        payload = self.model_dump(mode="json")
        payload["memory_rules"] = [
            "This snapshot contains only publishable Smallcaps.ai records published before the current RNS.",
            "Use source_id and published_at to identify the earlier disclosure behind a comparison.",
            "Do not treat different periods, units, currencies or accounting bases as directly comparable.",
            "Absence from this compact snapshot does not prove that a fact was never disclosed.",
        ]
        return payload


def _metric_series(
    records: Sequence[Mapping[str, object]],
) -> list[MemoryMetricSeries]:
    grouped: dict[str, list[MemoryMetricPoint]] = defaultdict(list)

    for record in records:
        source_id = _clean_text(record.get("source_id"))
        published_at = _iso(record.get("published_at"))
        title = _clean_text(record.get("title"))
        source_url = _clean_text(record.get("source_url"))
        for raw_fact in record.get("facts") or []:
            if not isinstance(raw_fact, Mapping):
                continue
            basis = _clean_text(raw_fact.get("basis") or "reported").lower()
            if basis not in {"reported", "calculated"}:
                continue
            metric = _clean_text(raw_fact.get("metric") or raw_fact.get("label"))
            label = _clean_text(raw_fact.get("label") or metric)
            value = _clean_text(raw_fact.get("value"))
            if not metric or not value or value.lower() == "not disclosed":
                continue
            period = _clean_text(raw_fact.get("period"))
            as_of_date = _clean_text(raw_fact.get("as_of_date"))
            unit = _clean_text(raw_fact.get("unit"))
            currency = _clean_text(raw_fact.get("currency"))
            key = _series_key(
                metric,
                period,
                as_of_date,
                unit,
                currency,
                basis,
            )
            if not key.split("|", 1)[0]:
                continue
            numeric = raw_fact.get("value_numeric")
            low = raw_fact.get("value_low")
            high = raw_fact.get("value_high")
            point = MemoryMetricPoint(
                source_id=source_id,
                published_at=published_at,
                title=title,
                source_url=source_url,
                label=label,
                metric=metric,
                period=period,
                value=value,
                value_numeric=(
                    float(numeric) if isinstance(numeric, (int, float)) else None
                ),
                value_low=float(low) if isinstance(low, (int, float)) else None,
                value_high=float(high) if isinstance(high, (int, float)) else None,
                unit=unit,
                currency=currency,
                as_of_date=as_of_date,
                basis=basis,
                note=_clean_text(raw_fact.get("note")),
            )
            duplicate = any(
                existing.source_id == point.source_id
                and existing.metric == point.metric
                and existing.period == point.period
                and existing.value == point.value
                for existing in grouped[key]
            )
            if not duplicate:
                grouped[key].append(point)

    ranked: list[tuple[int, MemoryMetricSeries]] = []
    for key, points in grouped.items():
        points.sort(key=lambda item: _parse_datetime(item.published_at))
        latest = points[-1]
        previous = points[-2] if len(points) > 1 else None
        direction: ChangeDirection = "unclear"
        absolute: float | None = None
        percent: float | None = None
        if (
            previous is not None
            and latest.value_numeric is not None
            and previous.value_numeric is not None
        ):
            absolute = latest.value_numeric - previous.value_numeric
            tolerance = max(abs(previous.value_numeric), 1.0) * 1e-9
            if abs(absolute) <= tolerance:
                direction = "flat"
            elif absolute > 0:
                direction = "up"
            else:
                direction = "down"
            if previous.value_numeric != 0:
                percent = absolute / abs(previous.value_numeric) * 100
        series = MemoryMetricSeries(
            key=key,
            metric=latest.metric,
            label=latest.label,
            period_family=_period_family(latest.period, latest.as_of_date),
            basis=latest.basis,
            unit=latest.unit,
            currency=latest.currency,
            latest_value=latest.value,
            previous_value=previous.value if previous is not None else "",
            change_direction=direction,
            change_absolute=absolute,
            change_percent=percent,
            points=points[-_MAX_POINTS_PER_SERIES:],
        )
        score = _metric_priority(latest.metric) + min(len(points), 4) * 8
        if len(points) > 1:
            score += 12
        if latest.basis == "reported":
            score += 3
        ranked.append((score, series))

    ranked.sort(
        key=lambda item: (
            item[0],
            _parse_datetime(item[1].points[-1].published_at),
        ),
        reverse=True,
    )
    return [series for _score, series in ranked[:_MAX_SERIES]]


def _current_guidance(
    records: Sequence[Mapping[str, object]],
) -> list[MemoryGuidanceItem]:
    current: dict[str, MemoryGuidanceItem] = {}
    for record in records:
        for raw_event in record.get("guidance") or []:
            if not isinstance(raw_event, Mapping):
                continue
            status = _clean_text(raw_event.get("status")).lower()
            metric = _clean_text(raw_event.get("metric"))
            if not metric or status in {"", "not-applicable", "not-disclosed"}:
                continue
            key = _guidance_key(raw_event)
            current[key] = MemoryGuidanceItem(
                key=key,
                source_id=_clean_text(record.get("source_id")),
                published_at=_iso(record.get("published_at")),
                title=_clean_text(record.get("title")),
                source_url=_clean_text(record.get("source_url")),
                metric=metric,
                period=_clean_text(raw_event.get("period")),
                value=_clean_text(raw_event.get("value")),
                status=status,
                comparator=_clean_text(raw_event.get("comparator")),
                previous_value=_clean_text(raw_event.get("previous_value")),
                note=_clean_text(raw_event.get("note")),
            )
    # Delivered and missed guidance are historical outcomes, not current forward
    # guidance. Withdrawn guidance remains visible because that is itself the
    # current guidance position.
    items = [
        item for item in current.values() if item.status not in {"delivered", "missed"}
    ]
    items.sort(
        key=lambda item: (
            _metric_priority(item.metric),
            _parse_datetime(item.published_at),
        ),
        reverse=True,
    )
    return items[:_MAX_GUIDANCE]


def _management_claims(
    records: Sequence[Mapping[str, object]],
) -> tuple[list[MemoryClaimItem], list[MemoryClaimItem]]:
    current: dict[str, MemoryClaimItem] = {}
    for record in records:
        for raw_claim in record.get("management_claims") or []:
            if not isinstance(raw_claim, Mapping):
                continue
            claim_text = _clean_text(raw_claim.get("claim"))
            if not claim_text:
                continue
            key = _claim_key(raw_claim)
            current[key] = MemoryClaimItem(
                key=key,
                source_id=_clean_text(record.get("source_id")),
                published_at=_iso(record.get("published_at")),
                title=_clean_text(record.get("title")),
                source_url=_clean_text(record.get("source_url")),
                claim=claim_text,
                metric=_clean_text(raw_claim.get("metric")),
                target_value=_clean_text(raw_claim.get("target_value")),
                target_date=_clean_text(raw_claim.get("target_date")),
                status=_clean_text(raw_claim.get("status") or "open").lower(),
                outcome=_clean_text(raw_claim.get("outcome")),
                evidence=_clean_text(raw_claim.get("evidence")),
            )
    open_items = [item for item in current.values() if item.status == "open"]
    resolved = [item for item in current.values() if item.status != "open"]
    open_items.sort(
        key=lambda item: (
            bool(item.target_date),
            item.target_date,
            item.published_at,
        ),
        reverse=True,
    )
    resolved.sort(key=lambda item: _parse_datetime(item.published_at), reverse=True)
    return open_items[:_MAX_CLAIMS], resolved[:_MAX_CLAIMS]


def _disclosure_gaps(
    records: Sequence[Mapping[str, object]],
) -> list[MemoryDisclosureGap]:
    seen: set[str] = set()
    output: list[MemoryDisclosureGap] = []
    # A historical gap should not live forever after its relevance has passed.
    # Carry forward only gaps raised in the latest few RNS analyses.
    for record in reversed(records[-_MAX_GAP_RECORDS:]):
        assessment = record.get("disclosure_assessment")
        if not isinstance(assessment, Mapping):
            continue
        for raw_item in assessment.get("missing_items") or []:
            item = _clean_text(raw_item)
            key = _normalise(item)
            if not item or not key or key in seen:
                continue
            seen.add(key)
            output.append(
                MemoryDisclosureGap(
                    item=item,
                    source_id=_clean_text(record.get("source_id")),
                    published_at=_iso(record.get("published_at")),
                    title=_clean_text(record.get("title")),
                    source_url=_clean_text(record.get("source_url")),
                )
            )
            if len(output) >= _MAX_GAPS:
                return output
    return output


def _impact_history(
    records: Sequence[Mapping[str, object]],
) -> list[MemoryImpactItem]:
    output: list[MemoryImpactItem] = []
    for record in reversed(records[-_MAX_IMPACT_HISTORY:]):
        score = record.get("impact_score")
        output.append(
            MemoryImpactItem(
                source_id=_clean_text(record.get("source_id")),
                published_at=_iso(record.get("published_at")),
                title=_clean_text(record.get("title")),
                source_url=_clean_text(record.get("source_url")),
                rns_type=_clean_text(record.get("rns_type")),
                impact_colour=_clean_text(record.get("impact_colour") or "grey"),
                impact_score=int(score) if isinstance(score, (int, float)) else 1,
                headline=_clean_text(record.get("headline") or record.get("title")),
                takeaway=_clean_text(record.get("takeaway")),
            )
        )
    return output


def build_company_memory(
    records: Sequence[Mapping[str, object]],
    *,
    ticker: str,
    company: str = "",
    before: datetime | None = None,
) -> CompanyMemorySnapshot:
    """Build a compact point-in-time company memory without another model call.

    The caller is responsible for supplying only eligible, publishable records that
    pre-date the announcement being analysed. This function ranks and compresses
    those records; it does not invent history or fetch outside information.
    """

    ordered = sorted(
        records,
        key=lambda item: _parse_datetime(item.get("published_at")),
    )
    dates = [
        parsed
        for item in ordered
        if (parsed := _parse_datetime(item.get("published_at"))).year
        != datetime.min.year
    ]
    coverage_since = dates[0].isoformat() if dates else ""
    latest_covered_at = dates[-1].isoformat() if dates else ""
    coverage_days = (
        max(0, (dates[-1].date() - dates[0].date()).days)
        if len(dates) >= 2
        else 0
    )
    status: CoverageStatus = (
        "established"
        if len(ordered) >= _ESTABLISHED_MIN_ANNOUNCEMENTS
        and coverage_days >= _ESTABLISHED_MIN_DAYS
        else "building"
    )
    open_claims, resolved_claims = _management_claims(ordered)
    if before is not None:
        if before.tzinfo is None:
            before = before.replace(tzinfo=timezone.utc)
        generated_before = before.astimezone(timezone.utc).isoformat()
    else:
        generated_before = ""
    return CompanyMemorySnapshot(
        ticker=_clean_text(ticker).upper(),
        company=_clean_text(company),
        generated_before=generated_before,
        coverage_status=status,
        coverage_since=coverage_since,
        latest_covered_at=latest_covered_at,
        coverage_days=coverage_days,
        announcement_count=len(ordered),
        current_guidance=_current_guidance(ordered),
        metric_series=_metric_series(ordered),
        open_management_claims=open_claims,
        resolved_management_claims=resolved_claims,
        disclosure_gaps=_disclosure_gaps(ordered),
        recent_impact_history=_impact_history(ordered),
    )
