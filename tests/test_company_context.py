from __future__ import annotations

from analyst.company_context import build_prior_context_record


def test_prior_context_separates_reported_calculated_and_interpretation() -> None:
    record = {
        "source_id": "spr-1",
        "published_at": "2026-08-21T07:00:00+01:00",
        "title": "Trading Update",
        "source_url": "https://example.invalid/spr-1",
        "source_urls": ["https://example.invalid/spr-1"],
        "rns_type": "Results & trading",
        "impact_colour": "green",
        "impact_score": 3,
        "impact_rationale": "Debt fell.",
        "headline": "Debt falls",
        "takeaway": "Net debt reduced.",
        "analyst_view": "This modestly strengthens the case.",
        "facts": [
            {
                "label": "Net debt",
                "metric": "net debt",
                "value": "£18m",
                "basis": "reported",
            },
            {
                "label": "Net debt reduction",
                "metric": "net debt change",
                "value": "25%",
                "basis": "calculated",
                "note": "Calculated from £24m to £18m.",
            },
            {
                "label": "Source warning",
                "metric": "source warning",
                "value": "Inconsistent date",
                "basis": "source-warning",
            },
        ],
        "guidance": [
            {
                "metric": "FY26 adjusted PBT",
                "period": "FY26",
                "value": "In line",
                "status": "reiterated",
            }
        ],
        "management_claims": [
            {
                "claim": "Complete land sale by June.",
                "claim_key": "spr-land-sale",
                "status": "open",
            }
        ],
        "supports_case": ["Debt fell."],
        "challenges_case": ["Guidance did not rise."],
        "watch_items": ["Cash conversion"],
        "disclosure_assessment": {
            "status": "partial",
            "missing_items": ["Working-capital detail"],
        },
    }

    context = build_prior_context_record(record)

    assert context["context_type"] == "prior_company_record"
    assert context["source_id"] == "spr-1"
    disclosure = context["company_disclosure"]
    assert [item["label"] for item in disclosure["reported_facts"]] == [
        "Net debt"
    ]
    assert disclosure["guidance_events"][0]["status"] == "reiterated"
    assert disclosure["management_claims"][0]["claim_key"] == "spr-land-sale"
    assert [item["label"] for item in context["smallcaps_calculations"]] == [
        "Net debt reduction"
    ]
    assert [item["label"] for item in context["source_caveats"]] == [
        "Source warning"
    ]
    assert context["prior_smallcaps_analysis"]["analyst_view"] == (
        "This modestly strengthens the case."
    )
    assert any(
        "must not be presented as company disclosure" in rule
        for rule in context["context_rules"]
    )
