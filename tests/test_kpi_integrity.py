from __future__ import annotations

import pytest

from product.kpi_integrity import metric_identity, period_profile, project_company_metrics


def _point(
    source_id: str,
    *,
    metric: str,
    label: str | None = None,
    period: str = "",
    value: str,
    value_numeric: float | None = None,
    value_low: float | None = None,
    value_high: float | None = None,
    unit: str = "",
    currency: str = "",
    as_of_date: str = "",
    basis: str = "reported",
    published_at: str = "2026-01-01T07:00:00+00:00",
    source_url: str | None = None,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "published_at": published_at,
        "title": f"Update {source_id}",
        "source_url": source_url if source_url is not None else f"https://example.invalid/{source_id}",
        "label": label or metric,
        "metric": metric,
        "period": period,
        "value": value,
        "value_numeric": value_numeric,
        "value_low": value_low,
        "value_high": value_high,
        "unit": unit,
        "currency": currency,
        "as_of_date": as_of_date,
        "basis": basis,
    }


def _series(*points: dict[str, object], metric: str | None = None) -> dict[str, object]:
    latest = points[-1]
    return {
        "metric": metric or str(latest["metric"]),
        "label": str(latest["label"]),
        "basis": str(latest["basis"]),
        "unit": str(latest["unit"]),
        "currency": str(latest["currency"]),
        "points": list(points),
    }


def test_safe_aliases_and_unit_scales_merge_without_changing_disclosed_values() -> None:
    output = project_company_metrics(
        [
            _series(
                _point(
                    "debt-1",
                    metric="net debt",
                    period="FY25",
                    value="£24.0m",
                    value_numeric=24.0,
                    unit="million",
                    currency="GBP",
                    published_at="2026-01-15T07:00:00+00:00",
                )
            ),
            _series(
                _point(
                    "debt-2",
                    metric="net borrowings",
                    period="H1 FY26",
                    value="£18,200k",
                    value_numeric=18_200.0,
                    unit="thousand",
                    currency="GBP",
                    published_at="2026-08-15T07:00:00+01:00",
                )
            ),
        ]
    )

    assert len(output) == 1
    debt = output[0]
    assert debt["identity"] == "net-debt"
    assert debt["label"] == "Net debt"
    assert debt["latest_value"] == "£18,200k"
    assert debt["previous_value"] == "£24.0m"
    assert debt["change_direction"] == "down"
    assert debt["change_percent"] == pytest.approx(-24.1667, rel=1e-3)
    assert [point["source_id"] for point in debt["trend_points"]] == ["debt-1", "debt-2"]
    assert [point["comparable_value_numeric"] for point in debt["trend_points"]] == [
        24_000_000.0,
        18_200_000.0,
    ]
    assert debt["integrity"]["status"] == "comparable"
    assert debt["integrity"]["provenance_complete"] is True


def test_stock_metrics_remain_point_in_time_when_labelled_by_reporting_period() -> None:
    fy = period_profile("FY26", instant_hint=metric_identity("net debt").instant)
    h1 = period_profile("H1 FY26", instant_hint=metric_identity("net debt").instant)
    revenue = period_profile("FY26", instant_hint=metric_identity("revenue").instant)

    assert fy.kind == "instant"
    assert fy.key == "POINT"
    assert h1.kind == "instant"
    assert revenue.kind == "duration"
    assert revenue.key == "FY"


def test_flow_periods_are_kept_separate_and_only_latest_family_is_published() -> None:
    output = project_company_metrics(
        [
            _series(
                _point(
                    "rev-h1",
                    metric="revenue",
                    period="H1 FY26",
                    value="£10m",
                    value_numeric=10.0,
                    unit="million",
                    currency="GBP",
                    published_at="2026-01-15T07:00:00+00:00",
                )
            ),
            _series(
                _point(
                    "rev-fy",
                    metric="group revenue",
                    period="FY26",
                    value="£25m",
                    value_numeric=25.0,
                    unit="£m",
                    published_at="2026-07-15T07:00:00+01:00",
                )
            ),
        ]
    )

    assert len(output) == 1
    revenue = output[0]
    assert revenue["identity"] == "revenue"
    assert revenue["period_family"] == "FY"
    assert revenue["previous_value"] == ""
    assert revenue["trend_points"] == []
    assert revenue["integrity"]["status"] == "single-point"
    assert revenue["integrity"]["suppressed_points"] == 1
    assert revenue["integrity"]["warnings"] == ["INCOMPATIBLE_PERIOD"]


def test_adjusted_and_unadjusted_profit_definitions_never_merge() -> None:
    output = project_company_metrics(
        [
            _series(
                _point(
                    "ebitda",
                    metric="EBITDA",
                    period="FY26",
                    value="£5m",
                    value_numeric=5.0,
                    unit="million",
                    currency="GBP",
                )
            ),
            _series(
                _point(
                    "adjusted-ebitda",
                    metric="Adjusted EBITDA",
                    period="FY26",
                    value="£7m",
                    value_numeric=7.0,
                    unit="million",
                    currency="GBP",
                )
            ),
        ]
    )

    assert {item["identity"] for item in output} == {"ebitda", "adjusted-ebitda"}


def test_currency_and_basis_mismatches_are_suppressed_not_compared() -> None:
    output = project_company_metrics(
        [
            _series(
                _point(
                    "gbp",
                    metric="revenue",
                    period="FY25",
                    value="£20m",
                    value_numeric=20.0,
                    unit="million",
                    currency="GBP",
                    published_at="2026-01-01T07:00:00+00:00",
                )
            ),
            _series(
                _point(
                    "usd",
                    metric="revenue",
                    period="FY26",
                    value="$25m",
                    value_numeric=25.0,
                    unit="million",
                    currency="USD",
                    published_at="2026-08-01T07:00:00+01:00",
                )
            ),
            _series(
                _point(
                    "calc",
                    metric="revenue",
                    period="FY27",
                    value="$30m",
                    value_numeric=30.0,
                    unit="million",
                    currency="USD",
                    basis="calculated",
                    published_at="2027-08-01T07:00:00+01:00",
                )
            ),
        ]
    )

    assert len(output) == 1
    revenue = output[0]
    assert revenue["latest_source_id"] == "calc"
    assert revenue["integrity"]["suppressed_points"] == 2
    assert revenue["integrity"]["warnings"] == [
        "INCOMPATIBLE_CURRENCY",
        "INCOMPATIBLE_BASIS",
    ]
    assert revenue["trend_points"] == []


def test_same_period_restatement_replaces_earlier_disclosure_but_is_audited() -> None:
    output = project_company_metrics(
        [
            _series(
                _point(
                    "prelim",
                    metric="revenue",
                    period="FY26",
                    value="£40m",
                    value_numeric=40.0,
                    unit="million",
                    currency="GBP",
                    published_at="2026-07-01T07:00:00+01:00",
                ),
                _point(
                    "annual-report",
                    metric="revenue",
                    period="FY26",
                    value="£41m",
                    value_numeric=41.0,
                    unit="million",
                    currency="GBP",
                    published_at="2026-08-01T07:00:00+01:00",
                ),
            )
        ]
    )

    revenue = output[0]
    assert revenue["latest_source_id"] == "annual-report"
    assert len(revenue["points"]) == 1
    assert revenue["integrity"]["deduplicated_points"] == 1
    assert revenue["integrity"]["suppressed_points"] == 0
    assert revenue["trend_points"] == []


def test_range_and_missing_provenance_never_draw_a_trend() -> None:
    ranged = project_company_metrics(
        [
            _series(
                _point(
                    "range-1",
                    metric="revenue",
                    period="FY25",
                    value="£20m",
                    value_numeric=20.0,
                    unit="million",
                    currency="GBP",
                ),
                _point(
                    "range-2",
                    metric="revenue",
                    period="FY26",
                    value="£24m–£26m",
                    value_low=24.0,
                    value_high=26.0,
                    unit="million",
                    currency="GBP",
                    published_at="2026-08-01T07:00:00+01:00",
                ),
            )
        ]
    )[0]
    assert ranged["integrity"]["status"] == "range-only"
    assert ranged["trend_points"] == []

    missing_source = project_company_metrics(
        [
            _series(
                _point(
                    "source-1",
                    metric="revenue",
                    period="FY25",
                    value="£20m",
                    value_numeric=20.0,
                    unit="million",
                    currency="GBP",
                ),
                _point(
                    "source-2",
                    metric="revenue",
                    period="FY26",
                    value="£25m",
                    value_numeric=25.0,
                    unit="million",
                    currency="GBP",
                    source_url="",
                    published_at="2026-08-01T07:00:00+01:00",
                ),
            )
        ]
    )[0]
    assert missing_source["integrity"]["status"] == "missing-provenance"
    assert missing_source["trend_points"] == []


def test_nonnumeric_status_series_are_not_promoted_to_key_numbers() -> None:
    output = project_company_metrics(
        [
            _series(
                _point(
                    "status-1",
                    metric="possible offer status",
                    period="Possible offer",
                    value="Preliminary discussions",
                ),
                _point(
                    "status-2",
                    metric="possible offer status",
                    period="Possible offer",
                    value="No firm offer",
                    published_at="2026-02-01T07:00:00+00:00",
                ),
            )
        ]
    )
    assert output == []
