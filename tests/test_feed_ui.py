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
            "The announcement indicates insolvency proceedings are imminent because "
            "the company has insufficient funds to continue as a going concern. "
            "This is a thesis-changing liquidity failure."
        ),
        "analyst_view": (
            "The highest-order issue is not the asset sale process but the explicit "
            "admission that the company lacks funds to keep trading. Once administration "
            "is being prepared, the relevant question shifts to residual asset value. "
            "A third sentence belongs in the full note."
        ),
        "headline": (
            "Trellus Health signals imminent administration amid going-concern shortfall"
        ),
        "takeaway": (
            "Trellus Health says it has insufficient funds to continue as a going "
            "concern and has filed a notice of intention to appoint administrators. "
            "The board expects no return to shareholders if any asset sale completes."
        ),
        "key_facts": [
            {
                "label": "Notice of intention to appoint administrators",
                "value": "Filed",
                "previous_value": "No administration notice disclosed",
                "basis": "reported",
            },
            {
                "label": "Going concern funding position",
                "value": "Insufficient funds to continue trading as a going concern",
                "comparator": "Not disclosed in supplied prior context",
                "basis": "reported",
            },
            {
                "label": "Potential shareholder recovery",
                "value": "No returns to shareholders expected if any sale is concluded",
                "comparator": "Not disclosed in supplied prior context",
                "basis": "reported",
            },
        ],
        "source_url": "https://example.com/rns",
        "price": None,
    }
    item.update(overrides)
    return item


def test_material_feed_markup_leads_with_outcome_verdict_and_semantic_signal() -> None:
    markup = _material_markup(_item())

    assert "Administration imminent; no shareholder return expected" in markup
    assert (
        "Trellus Health signals imminent administration amid going-concern shortfall"
        not in markup
    )
    assert "CRITICAL · ADVERSE" in markup
    assert "IMPACT CRITICAL" not in markup
    assert "· RED" not in markup
    assert ">Other<" not in markup
    assert markup.index("sca-feed-verdict") < markup.index("sca-evidence")
    assert markup.index("sca-evidence") < markup.index("sca-feed-view")


def test_feed_view_is_short_and_states_the_investment_consequence_first() -> None:
    markup = _material_markup(_item())

    assert "Thesis broken." in markup
    assert "insolvency and asset-recovery situation" in markup
    assert "The highest-order issue is not the asset sale process" not in markup
    assert "A third sentence belongs in the full note" not in markup


def test_feed_view_uses_concise_impact_rationale_for_normal_legacy_rows() -> None:
    markup = _material_markup(
        _item(
            headline="Net debt falls while guidance is maintained",
            takeaway="Net debt fell to £18.2m while guidance was unchanged.",
            impact_colour="green",
            impact_score=3,
            impact_level="high",
            impact_rationale="Lower debt reduces balance-sheet risk.",
            analyst_view="This is deliberately much longer analyst commentary.",
            key_facts=[{"label": "Net debt", "value": "£18.2m", "basis": "reported"}],
        )
    )

    assert "Lower debt reduces balance-sheet risk." in markup
    assert "deliberately much longer analyst commentary" not in markup


def test_feed_evidence_is_edited_for_scanability_without_losing_provenance() -> None:
    markup = _fact_markup(_item()["key_facts"])

    assert markup.count("sca-evidence-heading") == 1
    assert ">Evidence from the RNS<" in markup
    assert ">Administration<" in markup
    assert ">Notice of intention filed<" in markup
    assert ">Funding position<" in markup
    assert ">Shareholder recovery<" in markup
    assert "Previous / comparator:" not in markup
    assert "No administration notice disclosed" not in markup
    assert "Not disclosed in supplied prior context" not in markup
    assert "Reported" not in markup


def test_feed_keeps_meaningful_comparator_and_marks_calculations() -> None:
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

    assert "Previously: £24.0m" in markup
    assert markup.count("Smallcaps.ai calculation") == 1
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
            takeaway="",
            impact_rationale="",
            analyst_view="",
            key_facts=[],
        )
    )

    assert 'data-feed-kind="routine"' in markup
    assert "LOW · ROUTINE" in markup
    assert "Routine voting-rights denominator update" in markup
    assert "sca-evidence" not in markup


def test_feed_styles_create_one_dominant_and_clustered_action_group() -> None:
    source = Path("ui/feed.py").read_text(encoding="utf-8")

    assert '"Read analysis →"' in source
    assert 'type="primary"' in source
    assert '"☆ Watch"' in source
    assert '"Original RNS ↗"' in source
    assert "min-height:2.75rem" in FEED_CSS
    assert '[class*="st-key-feed-primary-"] button' in FEED_CSS
    assert "max-width:760px" in FEED_CSS
    assert "grid-template-columns:1fr" in FEED_CSS


def test_pass1_uses_native_system_typography() -> None:
    assert "fonts.googleapis.com" not in APP_CSS
    assert "-apple-system" in APP_CSS
