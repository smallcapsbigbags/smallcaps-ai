from __future__ import annotations

from ui.company import (
    _claims_markup,
    _gaps_markup,
    _guidance_markup,
    _metric_markup,
    _source_link,
)


def test_company_intelligence_metric_table_labels_calculated_change() -> None:
    markup = _metric_markup(
        [
            {
                "label": "Net debt",
                "metric": "net debt",
                "period_family": "Point in time",
                "basis": "reported",
                "latest_value": "£18.2m",
                "previous_value": "£24.0m",
                "change_direction": "down",
                "change_percent": -24.1667,
                "points": [
                    {
                        "source_id": "spr-1",
                        "published_at": "2026-08-21T07:00:00+01:00",
                        "title": "Trading Update",
                        "source_url": "https://example.invalid/spr-1",
                        "basis": "reported",
                    }
                ],
            }
        ]
    )

    assert "£18.2m" in markup
    assert "£24.0m" in markup
    assert "Down 24.2%" in markup
    assert "Smallcaps.ai calculation" in markup
    assert "Reported" in markup
    assert "Trading Update" in markup
    assert 'class="sca-table-wrap"' in markup


def test_company_intelligence_guidance_and_claims_retain_source_links() -> None:
    guidance = _guidance_markup(
        [
            {
                "metric": "FY26 adjusted PBT",
                "period": "FY26",
                "value": "In line with expectations",
                "status": "reiterated",
                "previous_value": "In line with expectations",
                "published_at": "2026-08-21T07:00:00+01:00",
                "title": "Trading Update",
                "source_url": "https://example.invalid/guidance",
            }
        ]
    )
    claims = _claims_markup(
        [
            {
                "claim": "Complete the land sale by June 2026.",
                "target_date": "June 2026",
                "status": "open",
                "published_at": "2026-01-15T07:00:00+00:00",
                "title": "Land sale update",
                "source_url": "https://example.invalid/claim",
            }
        ]
    )

    assert "Reiterated" in guidance
    assert "https://example.invalid/guidance" in guidance
    assert "Complete the land sale" in claims
    assert "Status: Open" in claims
    assert "https://example.invalid/claim" in claims


def test_company_intelligence_escapes_untrusted_database_text() -> None:
    markup = _gaps_markup(
        [
            {
                "item": '<script>alert("x")</script>',
                "published_at": "2026-08-21T07:00:00+01:00",
                "title": '<img src=x onerror=alert("x")>',
                "source_url": "https://example.invalid/safe",
            }
        ]
    )

    assert "<script>" not in markup
    assert "<img" not in markup
    assert "&lt;script&gt;" in markup
    assert "&lt;img" in markup


def test_company_intelligence_rejects_non_http_source_links() -> None:
    markup = _source_link(
        {
            "published_at": "2026-08-21T07:00:00+01:00",
            "title": "Source RNS",
            "source_url": "javascript:alert(1)",
        }
    )

    assert "javascript:" not in markup
    assert "href=" not in markup
    assert "Source RNS" in markup
