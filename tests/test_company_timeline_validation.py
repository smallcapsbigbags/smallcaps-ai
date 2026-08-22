from __future__ import annotations

from analyst.company_validation import validate_company_timeline


def _record(
    source_id: str,
    published_at: str,
    *,
    comparator_source_id: str = "",
) -> dict[str, object]:
    fact = {
        "label": "Net debt",
        "metric": "net debt",
        "period": "Point in time",
        "value": "£10m",
        "value_numeric": 10.0,
        "unit": "million",
        "currency": "GBP",
        "basis": "reported",
        "comparator": "",
        "comparator_type": "none",
        "comparator_source_id": comparator_source_id,
        "previous_value": "",
    }
    if comparator_source_id:
        fact.update(
            {
                "comparator": "Earlier net debt",
                "comparator_type": "prior-disclosure",
                "previous_value": "£12m",
            }
        )
    return {
        "source_id": source_id,
        "ticker": "SPR",
        "company": "Springfield Properties plc",
        "published_at": published_at,
        "title": f"Trading Update {source_id}",
        "raw_text": "Springfield reports its latest net debt position.",
        "source_url": f"https://example.invalid/{source_id}",
        "source_urls": [f"https://example.invalid/{source_id}"],
        "evidence_status": "complete",
        "rns_type": "Results & trading",
        "impact_colour": "amber",
        "impact_score": 2,
        "impact_rationale": "The balance sheet changed.",
        "headline": "Net debt updated",
        "takeaway": "The company reported its latest net debt position.",
        "facts": [fact],
        "guidance": [],
        "management_claims": [],
        "what_changed": {"coverage_status": "building"},
        "disclosure_assessment": {"status": "complete", "missing_items": []},
    }


def test_company_timeline_reconstructs_each_point_without_look_ahead() -> None:
    records = [
        _record("spr-3", "2026-08-21T07:00:00+00:00", comparator_source_id="spr-2"),
        _record("spr-1", "2026-01-15T07:00:00+00:00"),
        _record("spr-2", "2026-05-20T07:00:00+00:00", comparator_source_id="spr-1"),
    ]

    report = validate_company_timeline(
        records,
        ticker="SPR",
        company="Springfield Properties plc",
        history_limit=2,
    )

    assert report["valid"]
    assert report["errors"] == []
    assert report["checked_points"] == 3
    points = report["points"]
    assert points[0]["eligible_prior_count"] == 0
    assert points[1]["selected_prior_source_ids"] == ["spr-1"]
    assert points[2]["selected_prior_source_ids"] == ["spr-1", "spr-2"]
    assert all(point["valid"] for point in points)
    assert "spr-3" not in points[1]["selected_prior_source_ids"]


def test_company_timeline_rejects_untraceable_comparator_source() -> None:
    records = [
        _record("spr-1", "2026-01-15T07:00:00+00:00"),
        _record(
            "spr-2",
            "2026-05-20T07:00:00+00:00",
            comparator_source_id="future-or-invented-source",
        ),
    ]

    report = validate_company_timeline(
        records,
        ticker="SPR",
        company="Springfield Properties plc",
    )

    assert not report["valid"]
    assert any(
        "outside eligible history" in error for error in report["errors"]
    )


def test_company_timeline_rejects_duplicate_source_ids() -> None:
    records = [
        _record("spr-1", "2026-01-15T07:00:00+00:00"),
        _record("spr-1", "2026-05-20T07:00:00+00:00"),
    ]

    report = validate_company_timeline(
        records,
        ticker="SPR",
        company="Springfield Properties plc",
    )

    assert not report["valid"]
    assert any("duplicate source_id" in error for error in report["errors"])
