from __future__ import annotations

from datetime import datetime, timezone

import pytest

from analyst.company_memory import build_company_memory


def _record(
    source_id: str,
    published_at: str,
    *,
    facts: list[dict[str, object]] | None = None,
    guidance: list[dict[str, object]] | None = None,
    claims: list[dict[str, object]] | None = None,
    gaps: list[str] | None = None,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "published_at": published_at,
        "title": f"Update {source_id}",
        "source_url": f"https://example.invalid/{source_id}",
        "rns_type": "Results & trading",
        "impact_colour": "amber",
        "impact_score": 3,
        "headline": f"Analyst headline {source_id}",
        "takeaway": "Point-in-time analysis.",
        "facts": facts or [],
        "guidance": guidance or [],
        "management_claims": claims or [],
        "disclosure_assessment": {
            "status": "partial" if gaps else "complete",
            "missing_items": gaps or [],
        },
    }


def test_company_memory_tracks_comparable_metrics_guidance_and_promises() -> None:
    records = [
        _record(
            "spr-1",
            "2026-01-15T07:00:00+00:00",
            facts=[
                {
                    "label": "Net debt",
                    "metric": "net debt",
                    "period": "Point in time",
                    "value": "£24.0m",
                    "value_numeric": 24.0,
                    "unit": "million",
                    "currency": "GBP",
                    "as_of_date": "2025-12-31",
                    "basis": "reported",
                    "note": "Company reported net debt of £24.0m.",
                }
            ],
            guidance=[
                {
                    "metric": "FY26 adjusted PBT",
                    "period": "FY26",
                    "value": "In line with expectations",
                    "status": "maintained",
                    "previous_value": "In line with expectations",
                    "note": "No numerical range disclosed.",
                }
            ],
            claims=[
                {
                    "claim": "Management expects the land sale to complete by June 2026.",
                    "claim_key": "spr-land-sale-june-2026",
                    "metric": "land sale completion",
                    "target_date": "June 2026",
                    "status": "open",
                }
            ],
            gaps=["Cash available after working-capital commitments"],
        ),
        _record(
            "spr-2",
            "2026-08-21T07:00:00+01:00",
            facts=[
                {
                    "label": "Net debt",
                    "metric": "net debt",
                    "period": "Point in time",
                    "value": "£18.2m",
                    "value_numeric": 18.2,
                    "unit": "million",
                    "currency": "GBP",
                    "as_of_date": "2026-07-31",
                    "basis": "reported",
                    "note": "Company reported net debt of £18.2m.",
                }
            ],
            guidance=[
                {
                    "metric": "FY26 adjusted PBT",
                    "period": "FY26",
                    "value": "In line with expectations",
                    "status": "reiterated",
                    "previous_value": "In line with expectations",
                    "note": "Guidance was repeated.",
                }
            ],
            claims=[
                {
                    "claim": "The land sale completed in May 2026.",
                    "claim_key": "spr-land-sale-june-2026",
                    "metric": "land sale completion",
                    "target_date": "June 2026",
                    "status": "delivered",
                    "outcome": "Completed in May 2026.",
                }
            ],
            gaps=["Cash available after working-capital commitments"],
        ),
    ]

    memory = build_company_memory(
        records,
        ticker="SPR",
        company="Springfield Properties plc",
        before=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )

    assert memory.coverage_status == "building"
    assert memory.announcement_count == 2
    net_debt = next(item for item in memory.metric_series if item.metric == "net debt")
    assert net_debt.latest_value == "£18.2m"
    assert net_debt.previous_value == "£24.0m"
    assert net_debt.change_direction == "down"
    assert net_debt.change_percent == pytest.approx(-24.1667, rel=1e-3)

    guidance = memory.current_guidance[0]
    assert guidance.metric == "FY26 adjusted PBT"
    assert guidance.status == "reiterated"
    assert guidance.source_id == "spr-2"

    assert memory.open_management_claims == []
    assert memory.resolved_management_claims[0].key == "spr-land-sale-june-2026"
    assert memory.resolved_management_claims[0].status == "delivered"
    assert len(memory.disclosure_gaps) == 1

    context = memory.to_context_record()
    assert context["context_type"] == "company_memory_snapshot"
    assert context["generated_before"] == "2026-08-22T00:00:00+00:00"
    assert len(context["memory_rules"]) == 4


def test_company_memory_does_not_merge_non_comparable_periods() -> None:
    records = [
        _record(
            "abc-h1",
            "2026-01-01T07:00:00+00:00",
            facts=[
                {
                    "label": "Revenue",
                    "metric": "revenue",
                    "period": "H1 FY26",
                    "value": "£10m",
                    "value_numeric": 10.0,
                    "unit": "million",
                    "currency": "GBP",
                    "basis": "reported",
                }
            ],
        ),
        _record(
            "abc-fy",
            "2026-07-01T07:00:00+01:00",
            facts=[
                {
                    "label": "Revenue",
                    "metric": "revenue",
                    "period": "FY26",
                    "value": "£25m",
                    "value_numeric": 25.0,
                    "unit": "million",
                    "currency": "GBP",
                    "basis": "reported",
                }
            ],
        ),
    ]

    memory = build_company_memory(records, ticker="ABC")
    revenue_series = [item for item in memory.metric_series if item.metric == "revenue"]

    assert len(revenue_series) == 2
    assert {item.period_family for item in revenue_series} == {"H1", "FY"}
    assert all(item.previous_value == "" for item in revenue_series)


def test_company_memory_requires_six_announcements_and_twelve_months_for_established() -> None:
    records = [
        _record("x1", "2025-01-01T07:00:00+00:00"),
        _record("x2", "2025-03-01T07:00:00+00:00"),
        _record("x3", "2025-06-01T07:00:00+01:00"),
        _record("x4", "2025-09-01T07:00:00+01:00"),
        _record("x5", "2025-12-01T07:00:00+00:00"),
        _record("x6", "2026-01-02T07:00:00+00:00"),
    ]

    memory = build_company_memory(records, ticker="XYZ")

    assert memory.coverage_status == "established"
    assert memory.coverage_days == 366
