from __future__ import annotations

from pathlib import Path

from ui.common import APP_CSS
from ui.feed import _fact_markup, _material_markup, _routine_markup
from ui.feed_styles import FEED_CSS


def _item(**overrides):
    item = {
        "source_id": "trls-test",
        "ticker": "TRLS",
        "company": "Trellus Health plc",
        "published_at": "2026-08-21T07:00:00+01:00",
        "rns_type": "Other",
        "impact_colour": "red",
        "impact_score": 5,
        "impact_level": "critical",
        "impact_rationale": (
            "The company cannot fund continued trading and expects no shareholder recovery."
        ),
        "headline": "Administration imminent; no shareholder return expected",
        "takeaway": (
            "Trellus has insufficient funds to continue as a going concern and has filed "
            "notice of its intention to appoint administrators."
        ),
        "key_facts": [
            {
                "label": "Administration",
                "value": "Notice of intention filed",
                "basis": "reported",
            },
            {
                "label": "Funding position",
                "value": "Insufficient to continue as a going concern",
                "basis": "reported",
            },
            {
                "label": "Shareholder recovery",
                "value": "No return expected from any asset sale",
                "basis": "reported",
            },
        ],
        "source_url": "https://example.com/rns",
        "price": None,
    }
    item.update(overrides)
    return item


def test_material_feed_markup_leads_with_verdict_and_semantic_signal() -> None:
    markup = _material_markup(_item())

    assert "Administration imminent; no shareholder return expected" in markup
    assert "CRITICAL · ADVERSE" in markup
    assert "IMPACT CRITICAL" not in markup
    assert "· RED" not in markup
    assert ">Other<" not in markup
    assert markup.index("sca-feed-verdict") < markup.index("sca-evidence")
    assert markup.index("sca-evidence") < markup.index("sca-feed-view")


def test_feed_evidence_labels_reported_section_once_and_marks_calculations() -> None:
    markup = _fact_markup(
        [
            {
                "label": "Net debt",
                "value": "£18.2m",
                "value_numeric": 18.2,
                "previous_value": "£24.0m",
                "basis": "reported",
            },
            {
                "label": "Net debt reduction",
                "value": "24.2%",
                "value_numeric": 24.2,
                "basis": "calculated",
            },
        ]
    )

    assert markup.count("sca-evidence-heading") == 1
    assert ">Evidence<" in markup
    assert "Reported" not in markup
    assert markup.count("Smallcaps.ai calculation") == 1
    assert "Previous / comparator: £24.0m" in markup
    assert markup.count("sca-evidence-value-numeric") == 2


def test_feed_narrative_evidence_uses_sans_serif_and_escapes_text() -> None:
    markup = _fact_markup(
        [
            {
                "label": '<script>alert("label")</script>',
                "value": '<img src=x onerror=alert("value")>',
                "basis": "reported",
            }
        ]
    )

    assert "sca-evidence-grid-narrative" in markup
    assert "sca-evidence-value-numeric" not in markup
    assert "<script>" not in markup
    assert "<img" not in markup
    assert "&lt;script&gt;" in markup
    assert "&lt;img" in markup


def test_routine_feed_markup_is_compact_and_accessible() -> None:
    markup = _routine_markup(
        _item(
            impact_colour="grey",
            impact_score=1,
            impact_level="low",
            headline="Routine voting-rights denominator update",
            rns_type="Share capital",
        )
    )

    assert 'data-feed-kind="routine"' in markup
    assert "LOW · ROUTINE" in markup
    assert "Routine voting-rights denominator update" in markup
    assert "sca-evidence" not in markup


def test_feed_styles_create_one_dominant_mobile_action() -> None:
    source = Path("ui/feed.py").read_text(encoding="utf-8")

    assert '"Read analysis →"' in source
    assert 'type="primary"' in source
    assert '"☆ Watch"' in source
    assert '"Original RNS ↗"' in source
    assert "min-height:2.75rem" in FEED_CSS
    assert '[class*="st-key-feed-primary-"] button' in FEED_CSS
    assert "grid-template-columns:1fr" in FEED_CSS


def test_pass1_uses_native_system_typography() -> None:
    assert "fonts.googleapis.com" not in APP_CSS
    assert "-apple-system" in APP_CSS
