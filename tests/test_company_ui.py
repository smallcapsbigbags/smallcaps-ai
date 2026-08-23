from __future__ import annotations

from ui.company import (
    _claims_markup,
    _gaps_markup,
    _guidance_markup,
    _metric_cards_markup,
    _source_anchor,
)


def test_company_intelligence_metric_cards_keep_comparison_and_provenance() -> None:
    markup = _metric_cards_markup(
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
    assert "Reported" in markup
    assert "Latest RNS ↗" in markup
    assert 'class="sca-company-metric"' in markup


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
    assert "Target: June 2026" in claims
    assert "https://example.invalid/claim" in claims


def test_company_intelligence_escapes_untrusted_database_text() -> None:
    gaps = _gaps_markup(
        [
            {
                "item": '<script>alert("x")</script>',
                "published_at": "2026-08-21T07:00:00+01:00",
                "title": '<img src=x onerror=alert("x")>',
                "source_url": "https://example.invalid/safe",
            }
        ]
    )
    claims = _claims_markup(
        [
            {
                "claim": '<script>alert("claim")</script>',
                "target_date": '<img src=x onerror=alert("target")>',
                "source_url": "https://example.invalid/claim",
            }
        ]
    )

    assert "<script>" not in gaps
    assert "&lt;script&gt;" in gaps
    assert "<script>" not in claims
    assert "&lt;script&gt;" in claims
    assert "<img" not in claims
    assert "&lt;img" in claims


def test_company_intelligence_rejects_non_http_source_links() -> None:
    markup = _source_anchor(
        {
            "published_at": "2026-08-21T07:00:00+01:00",
            "title": "Source RNS",
            "source_url": "javascript:alert(1)",
        },
        "Source RNS",
    )

    assert markup == ""
