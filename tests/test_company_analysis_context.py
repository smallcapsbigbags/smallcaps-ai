from __future__ import annotations

from datetime import datetime, timezone

from analyst.company_context import build_company_analysis_context
from analyst.models import AnnouncementInput


def _record(source_id: str, published_at: str, *, ticker: str = "SPR") -> dict[str, object]:
    return {
        "source_id": source_id,
        "ticker": ticker,
        "published_at": published_at,
        "title": f"RNS {source_id}",
        "source_url": f"https://example.invalid/{source_id}",
        "source_urls": [f"https://example.invalid/{source_id}"],
        "rns_type": "Results & trading",
        "impact_colour": "amber",
        "impact_score": 2,
        "headline": f"Analysis {source_id}",
        "takeaway": "A prior company update.",
        "facts": [
            {
                "label": "Net debt",
                "metric": "net debt",
                "period": "Point in time",
                "value": "£10m",
                "value_numeric": 10.0,
                "unit": "million",
                "currency": "GBP",
                "basis": "reported",
            }
        ],
        "guidance": [],
        "management_claims": [],
        "disclosure_assessment": {"status": "complete", "missing_items": []},
    }


def _announcement() -> AnnouncementInput:
    return AnnouncementInput(
        source_id="spr-current",
        ticker="SPR",
        company="Springfield Properties plc",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Share Buyback and Rule 9 Waiver",
        text="Springfield proposes a share buyback and seeks a Rule 9 waiver.",
        rns_type="Share capital",
    )


def test_company_analysis_context_rejects_current_future_duplicate_and_wrong_ticker() -> None:
    records = [
        _record("spr-1", "2026-01-15T07:00:00+00:00"),
        _record("spr-2", "2026-05-20T07:00:00+00:00"),
        _record("spr-1", "2026-02-01T07:00:00+00:00"),
        _record("spr-current", "2026-08-21T07:00:00+00:00"),
        _record("spr-future", "2026-08-22T07:00:00+00:00"),
        _record("other-company", "2026-03-01T07:00:00+00:00", ticker="XYZ"),
    ]

    bundle = build_company_analysis_context(records, _announcement(), history_limit=2)

    assert [item["source_id"] for item in bundle.eligible_records] == [
        "spr-1",
        "spr-2",
    ]
    assert bundle.selected_source_ids == ("spr-1", "spr-2")
    assert set(bundle.rejected_source_ids) == {
        "spr-1",
        "spr-current",
        "spr-future",
        "other-company",
    }
    assert bundle.memory is not None
    assert bundle.memory.announcement_count == 2
    assert bundle.memory.generated_before == "2026-08-21T07:00:00+00:00"
    assert bundle.expected_coverage_status == "building"
    assert bundle.context_records[0]["context_type"] == "company_memory_snapshot"
    assert all(
        item.get("source_id") != "spr-current"
        for item in bundle.context_records[1:]
    )


def test_company_analysis_context_is_empty_for_first_covered_rns() -> None:
    bundle = build_company_analysis_context([], _announcement())

    assert bundle.memory is None
    assert bundle.context_records == ()
    assert bundle.selected_source_ids == ()
    assert bundle.expected_coverage_status == "building"
