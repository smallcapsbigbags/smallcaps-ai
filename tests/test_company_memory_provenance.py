from __future__ import annotations

from analyst.company_memory import build_company_memory


def _record(
    source_id: str,
    day: int,
    *,
    facts: list[dict[str, object]] | None = None,
    guidance: list[dict[str, object]] | None = None,
    gaps: list[str] | None = None,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "published_at": f"2026-01-{day:02d}T07:00:00+00:00",
        "title": f"Update {source_id}",
        "source_url": f"https://example.invalid/{source_id}",
        "impact_colour": "grey",
        "impact_score": 1,
        "headline": f"Update {source_id}",
        "facts": facts or [],
        "guidance": guidance or [],
        "management_claims": [],
        "disclosure_assessment": {
            "status": "partial" if gaps else "complete",
            "missing_items": gaps or [],
        },
    }


def test_reported_and_calculated_metrics_remain_separate_series() -> None:
    records = [
        _record(
            "reported",
            1,
            facts=[
                {
                    "label": "EBITDA margin",
                    "metric": "EBITDA margin",
                    "period": "FY25",
                    "value": "12.0%",
                    "value_numeric": 12.0,
                    "unit": "%",
                    "basis": "reported",
                }
            ],
        ),
        _record(
            "calculated",
            2,
            facts=[
                {
                    "label": "EBITDA margin",
                    "metric": "EBITDA margin",
                    "period": "FY26",
                    "value": "11.0%",
                    "value_numeric": 11.0,
                    "unit": "%",
                    "basis": "calculated",
                    "note": "Calculated from £4.4m EBITDA / £40.0m revenue = 11.0%.",
                }
            ],
        ),
    ]

    memory = build_company_memory(records, ticker="ABC")
    margin_series = [
        item for item in memory.metric_series if item.metric == "EBITDA margin"
    ]

    assert len(margin_series) == 2
    assert {item.basis for item in margin_series} == {"reported", "calculated"}
    assert all(item.previous_value == "" for item in margin_series)


def test_delivered_guidance_is_removed_from_current_forward_guidance() -> None:
    records = [
        _record(
            "guidance-issued",
            1,
            guidance=[
                {
                    "metric": "FY26 revenue",
                    "period": "FY26",
                    "value": "£40m-£42m",
                    "status": "issued",
                }
            ],
        ),
        _record(
            "guidance-delivered",
            2,
            guidance=[
                {
                    "metric": "FY26 revenue",
                    "period": "FY26",
                    "value": "£41m",
                    "status": "delivered",
                    "previous_value": "£40m-£42m",
                }
            ],
        ),
    ]

    memory = build_company_memory(records, ticker="ABC")

    assert memory.current_guidance == []


def test_disclosure_gaps_only_carry_forward_from_recent_records() -> None:
    records = [
        _record("old-gap", 1, gaps=["Old one-off disclosure gap"]),
        _record("recent-1", 2),
        _record("recent-2", 3),
        _record("recent-3", 4, gaps=["Current funding detail"]),
    ]

    memory = build_company_memory(records, ticker="ABC")

    assert [item.item for item in memory.disclosure_gaps] == [
        "Current funding detail"
    ]
