from __future__ import annotations

from jobs.validate_company_memory import validate_snapshot


def _snapshot() -> dict[str, object]:
    return {
        "ticker": "SPR",
        "company": "Springfield Properties plc",
        "generated_before": "2026-08-22T07:00:00+00:00",
        "coverage_status": "building",
        "announcement_count": 2,
        "coverage_days": 220,
        "current_guidance": [
            {
                "key": "fy26 adjusted pbt|fy26",
                "source_id": "spr-2",
                "metric": "FY26 adjusted PBT",
            }
        ],
        "metric_series": [
            {
                "key": "net debt|point in time|million|gbp|reported",
                "metric": "net debt",
                "basis": "reported",
                "latest_value": "£18.2m",
                "previous_value": "£24.0m",
                "points": [
                    {
                        "source_id": "spr-1",
                        "published_at": "2026-01-15T07:00:00+00:00",
                        "value": "£24.0m",
                        "basis": "reported",
                    },
                    {
                        "source_id": "spr-2",
                        "published_at": "2026-08-21T07:00:00+00:00",
                        "value": "£18.2m",
                        "basis": "reported",
                    },
                ],
            }
        ],
        "open_management_claims": [
            {
                "key": "spr-buyback-authority",
                "source_id": "spr-2",
            }
        ],
        "resolved_management_claims": [],
        "disclosure_gaps": [],
    }


def test_company_memory_validation_accepts_valid_snapshot() -> None:
    report = validate_snapshot(_snapshot())

    assert report["valid"]
    assert report["errors"] == []
    assert report["comparable_series_count"] == 1
    assert report["source_id_count"] == 2


def test_company_memory_validation_detects_future_leak_and_bad_coverage_status() -> None:
    snapshot = _snapshot()
    snapshot["coverage_status"] = "established"
    snapshot["metric_series"][0]["points"][-1]["published_at"] = (
        "2026-08-22T07:00:00+00:00"
    )

    report = validate_snapshot(snapshot)

    assert not report["valid"]
    assert any("coverage_status" in error for error in report["errors"])
    assert any("at or after generated_before" in error for error in report["errors"])


def test_company_memory_validation_detects_mixed_basis_and_duplicate_claims() -> None:
    snapshot = _snapshot()
    snapshot["metric_series"][0]["points"][-1]["basis"] = "calculated"
    snapshot["resolved_management_claims"] = [
        {
            "key": "spr-buyback-authority",
            "source_id": "spr-1",
        }
    ]

    report = validate_snapshot(snapshot)

    assert not report["valid"]
    assert any("mixes basis" in error for error in report["errors"])
    assert any("appears more than once" in error for error in report["errors"])
