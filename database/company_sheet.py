from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session, sessionmaker

from analyst.monitoring_sheet import monitoring_signal_from_colour
from database.company_intelligence import CompanyIntelligenceRepository
from database.monitoring import MonitoringSheetRepository
from database.product import ProductRepository
from product.company_sheet import (
    CompanyClaim,
    CompanyCoverage,
    CompanyDisclosureGap,
    CompanyGuidanceItem,
    CompanyMetricIntegrity,
    CompanyMetricPoint,
    CompanyMetricSeries,
    CompanySheet,
    CompanyTimelineItem,
)
from product.kpi_integrity import project_company_metrics
from product.monitoring import (
    MonitoringImpact,
    market_reaction_from_price,
)


class CompanySheetRepository:
    """Compose Company Memory into the public SmallcapsBigBags research sheet."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.product = ProductRepository(session_factory)
        self.intelligence = CompanyIntelligenceRepository(session_factory)
        self.monitoring = MonitoringSheetRepository(session_factory)

    def get_company(self, ticker: str, *, history_limit: int = 200) -> CompanySheet | None:
        clean_ticker = _normalise_ticker(ticker)
        if not clean_ticker:
            return None

        history = self.product.company_history(clean_ticker, limit=history_limit)
        memory = self.intelligence.get_company_intelligence(clean_ticker)
        if history is None or memory is None:
            return None

        announcements = list(history.get("announcements") or [])
        current_position = None
        if announcements:
            source_id = str(announcements[0].get("source_id") or "").strip()
            if source_id:
                current_position = self.monitoring.get_detail(source_id)

        guidance = [
            _guidance_item(item)
            for item in list(memory.get("current_guidance") or [])
            if isinstance(item, dict) and str(item.get("metric") or "").strip()
        ]
        raw_metrics = [
            item
            for item in list(memory.get("metric_series") or [])
            if isinstance(item, dict)
        ]
        metrics = [
            _metric_series(item)
            for item in project_company_metrics(raw_metrics)
        ]
        open_claims = [
            _claim_item(item)
            for item in list(memory.get("open_management_claims") or [])
            if isinstance(item, dict) and str(item.get("claim") or "").strip()
        ]
        resolved_claims = [
            _claim_item(item)
            for item in list(memory.get("resolved_management_claims") or [])
            if isinstance(item, dict) and str(item.get("claim") or "").strip()
        ]
        gaps = [
            _gap_item(item)
            for item in list(memory.get("disclosure_gaps") or [])
            if isinstance(item, dict) and str(item.get("item") or "").strip()
        ]
        timeline = [
            _timeline_item(item)
            for item in announcements
            if isinstance(item, dict) and str(item.get("source_id") or "").strip()
        ]

        coverage_status = str(memory.get("coverage_status") or "building").strip()
        if coverage_status not in {"building", "established"}:
            coverage_status = "building"

        return CompanySheet(
            generated_at=datetime.now(timezone.utc),
            ticker=str(history.get("ticker") or clean_ticker),
            company=str(history.get("company") or memory.get("company") or ""),
            market=str(history.get("market") or "AIM"),
            isin=str(history.get("isin") or ""),
            coverage=CompanyCoverage(
                status=coverage_status,  # type: ignore[arg-type]
                coverage_since=str(
                    memory.get("coverage_since")
                    or history.get("coverage_since")
                    or ""
                ),
                latest_covered_at=str(memory.get("latest_covered_at") or ""),
                coverage_days=max(0, int(memory.get("coverage_days") or 0)),
                announcement_count=max(
                    0,
                    int(
                        history.get("announcement_count")
                        or memory.get("announcement_count")
                        or 0
                    ),
                ),
            ),
            current_position=current_position,
            guidance=guidance,
            metrics=metrics,
            open_management_claims=open_claims,
            resolved_management_claims=resolved_claims,
            disclosure_gaps=gaps,
            history=timeline,
            has_more_history=bool(history.get("has_more")),
        )


def _normalise_ticker(value: object) -> str:
    return str(value or "").upper().strip().replace(".L", "").rstrip(".-")


def _impact_level(value: object, score: int) -> str:
    clean = str(value or "").strip().lower()
    if clean in {"low", "medium", "high", "critical"}:
        return clean
    if score >= 5:
        return "critical"
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


def _guidance_item(item: dict[str, Any]) -> CompanyGuidanceItem:
    return CompanyGuidanceItem(
        key=str(item.get("key") or ""),
        source_id=str(item.get("source_id") or ""),
        published_at=str(item.get("published_at") or ""),
        title=str(item.get("title") or ""),
        source_url=str(item.get("source_url") or ""),
        metric=str(item.get("metric") or "Guidance"),
        period=str(item.get("period") or ""),
        value=str(item.get("value") or ""),
        status=str(item.get("status") or "not-disclosed"),
        comparator=str(item.get("comparator") or ""),
        previous_value=str(item.get("previous_value") or ""),
        note=str(item.get("note") or ""),
    )


def _period_type(value: object) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in {"instant", "duration", "event", "unknown"} else "unknown"


def _trend_status(value: object) -> str:
    clean = str(value or "").strip().lower()
    return (
        clean
        if clean
        in {
            "comparable",
            "single-point",
            "range-only",
            "insufficient-period",
            "missing-provenance",
            "non-numeric",
        }
        else "single-point"
    )


def _metric_point(item: dict[str, Any]) -> CompanyMetricPoint:
    return CompanyMetricPoint(
        source_id=str(item.get("source_id") or ""),
        published_at=str(item.get("published_at") or ""),
        title=str(item.get("title") or ""),
        source_url=str(item.get("source_url") or ""),
        label=str(item.get("label") or item.get("metric") or "Metric"),
        metric=str(item.get("metric") or item.get("label") or "Metric"),
        identity=str(item.get("identity") or ""),
        period=str(item.get("period") or ""),
        period_family=str(item.get("period_family") or ""),
        period_type=_period_type(item.get("period_type")),  # type: ignore[arg-type]
        period_end=str(item.get("period_end") or ""),
        value=str(item.get("value") or ""),
        value_numeric=_optional_float(item.get("value_numeric")),
        value_low=_optional_float(item.get("value_low")),
        value_high=_optional_float(item.get("value_high")),
        unit=str(item.get("unit") or ""),
        unit_family=str(item.get("unit_family") or ""),
        unit_scale=_positive_float(item.get("unit_scale"), default=1.0),
        comparable_value_numeric=_optional_float(
            item.get("comparable_value_numeric")
        ),
        currency=str(item.get("currency") or ""),
        as_of_date=str(item.get("as_of_date") or ""),
        basis=str(item.get("basis") or "reported"),
        note=str(item.get("note") or ""),
    )


def _metric_integrity(item: dict[str, Any]) -> CompanyMetricIntegrity:
    return CompanyMetricIntegrity(
        version="kpi-integrity-v1",
        status=_trend_status(item.get("status")),  # type: ignore[arg-type]
        reason=str(item.get("reason") or ""),
        identity=str(item.get("identity") or ""),
        period_family=str(item.get("period_family") or ""),
        period_type=_period_type(item.get("period_type")),  # type: ignore[arg-type]
        unit_family=str(item.get("unit_family") or ""),
        currency=str(item.get("currency") or ""),
        basis=str(item.get("basis") or "reported"),
        total_points=_non_negative_int(item.get("total_points")),
        selected_points=_non_negative_int(item.get("selected_points")),
        comparable_points=_non_negative_int(item.get("comparable_points")),
        source_count=_non_negative_int(item.get("source_count")),
        suppressed_points=_non_negative_int(item.get("suppressed_points")),
        suppressed_series=_non_negative_int(item.get("suppressed_series")),
        deduplicated_points=_non_negative_int(item.get("deduplicated_points")),
        provenance_complete=bool(item.get("provenance_complete")),
        warnings=[
            str(value)
            for value in list(item.get("warnings") or [])
            if str(value).strip()
        ],
    )


def _metric_series(item: dict[str, Any]) -> CompanyMetricSeries:
    direction = str(item.get("change_direction") or "unclear").strip().lower()
    if direction not in {"up", "down", "flat", "unclear"}:
        direction = "unclear"
    points = [
        _metric_point(point)
        for point in list(item.get("points") or [])
        if isinstance(point, dict)
    ]
    trend_points = [
        _metric_point(point)
        for point in list(item.get("trend_points") or [])
        if isinstance(point, dict)
    ]
    integrity = (
        item.get("integrity")
        if isinstance(item.get("integrity"), dict)
        else {}
    )
    return CompanyMetricSeries(
        key=str(item.get("key") or ""),
        identity=str(item.get("identity") or ""),
        metric=str(item.get("metric") or item.get("label") or "Metric"),
        label=str(item.get("label") or item.get("metric") or "Metric"),
        period_family=str(item.get("period_family") or ""),
        period_type=_period_type(item.get("period_type")),  # type: ignore[arg-type]
        basis=str(item.get("basis") or "reported"),
        unit=str(item.get("unit") or ""),
        unit_family=str(item.get("unit_family") or ""),
        currency=str(item.get("currency") or ""),
        latest_value=str(item.get("latest_value") or ""),
        previous_value=str(item.get("previous_value") or ""),
        latest_source_id=str(item.get("latest_source_id") or ""),
        latest_source_url=str(item.get("latest_source_url") or ""),
        previous_source_id=str(item.get("previous_source_id") or ""),
        previous_source_url=str(item.get("previous_source_url") or ""),
        change_direction=direction,  # type: ignore[arg-type]
        change_absolute=_optional_float(item.get("change_absolute")),
        change_percent=_optional_float(item.get("change_percent")),
        points=points,
        trend_points=trend_points,
        integrity=_metric_integrity(integrity),
    )


def _claim_item(item: dict[str, Any]) -> CompanyClaim:
    return CompanyClaim(
        key=str(item.get("key") or ""),
        source_id=str(item.get("source_id") or ""),
        published_at=str(item.get("published_at") or ""),
        title=str(item.get("title") or ""),
        source_url=str(item.get("source_url") or ""),
        claim=str(item.get("claim") or ""),
        metric=str(item.get("metric") or ""),
        target_value=str(item.get("target_value") or ""),
        target_date=str(item.get("target_date") or ""),
        status=str(item.get("status") or "open"),
        outcome=str(item.get("outcome") or ""),
        evidence=str(item.get("evidence") or ""),
    )


def _gap_item(item: dict[str, Any]) -> CompanyDisclosureGap:
    return CompanyDisclosureGap(
        item=str(item.get("item") or ""),
        source_id=str(item.get("source_id") or ""),
        published_at=str(item.get("published_at") or ""),
        title=str(item.get("title") or ""),
        source_url=str(item.get("source_url") or ""),
    )


def _timeline_item(item: dict[str, Any]) -> CompanyTimelineItem:
    score = max(1, min(5, int(item.get("impact_score") or 1)))
    source_id = str(item.get("source_id") or "")
    return CompanyTimelineItem(
        source_id=source_id,
        published_at=item.get("published_at"),
        rns_type=str(item.get("rns_type") or ""),
        signal=monitoring_signal_from_colour(str(item.get("impact_colour") or "grey")),
        headline=str(item.get("headline") or item.get("takeaway") or "RNS update"),
        takeaway=str(item.get("takeaway") or ""),
        market_reaction=market_reaction_from_price(
            item.get("price") if isinstance(item.get("price"), dict) else None
        ),
        impact=MonitoringImpact(
            score=score,
            level=_impact_level(item.get("impact_level"), score),  # type: ignore[arg-type]
        ),
        detail_url=f"/api/v1/monitoring/{quote(source_id, safe='')}",
        original_source_url=str(item.get("source_url") or ""),
    )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_float(value: object, *, default: float) -> float:
    parsed = _optional_float(value)
    return parsed if parsed is not None and parsed > 0 else default


def _non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
