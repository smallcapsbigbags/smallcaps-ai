from pathlib import Path

from ui.beta import BETA_CSS
from ui.company import (
    _coverage_line,
    _current_position_markup,
    _gaps_markup,
    _guidance_markup,
    _metric_cards_markup,
    _metric_series_is_displayable,
    _timeline_markup,
)
from ui.company_styles import COMPANY_CSS


def _latest_note():
    return {
        "ticker": "SPR",
        "company": "Springfield Properties plc",
        "published_at": "2026-08-21T08:00:00+01:00",
        "rns_type": "Corporate",
        "impact_colour": "green",
        "impact_level": "high",
        "headline": "Meaningful buyback authority could retire about 10% of shares",
        "takeaway": "Springfield is asking shareholders to approve a material buyback.",
        "analyst_view": (
            "This is a meaningful potential catalyst rather than a token authority. "
            "The key question is how much cash can be returned without weakening the balance sheet."
        ),
        "key_facts": [],
        "what_changed": {},
        "price": None,
    }


def test_company_coverage_line_is_quiet_and_honest() -> None:
    history = {
        "announcement_count": 2,
        "coverage_since": "2026-08-01T08:00:00+01:00",
    }
    assert _coverage_line(history, {"coverage_status": "building"}) == (
        "Coverage since 1 Aug 2026 · 2 analysed RNSs · history still building"
    )
    assert _coverage_line(
        {"announcement_count": 1, "coverage_since": ""},
        {"coverage_status": "established"},
    ) == "1 analysed RNS · established history"


def test_company_current_position_leads_with_investment_view() -> None:
    markup = _current_position_markup(_latest_note())
    assert 'data-company-section="current-position"' in markup
    assert "Current position" in markup
    assert "Meaningful buyback authority could retire about 10% of shares" in markup
    assert "meaningful potential catalyst" in markup
    assert "Latest Smallcaps.ai view" in markup
    assert "HIGH · FAVOURABLE" in markup


def test_company_guidance_and_metrics_present_decision_useful_information() -> None:
    guidance = _guidance_markup(
        [
            {
                "metric": "adjusted profit",
                "period": "FY27",
                "value": "£14.0m",
                "status": "maintained",
                "previous_value": "£14.0m",
                "source_url": "https://example.com/rns",
            }
        ]
    )
    assert "adjusted profit" in guidance
    assert "£14.0m" in guidance
    assert "Maintained" in guidance
    assert "RNS ↗" in guidance
    assert "Previous</div>" not in guidance

    metrics = _metric_cards_markup(
        [
            {
                "label": "Net debt",
                "latest_value": "£18.2m",
                "previous_value": "£24.0m",
                "change_direction": "down",
                "change_percent": -24.166,
                "basis": "reported",
                "points": [
                    {
                        "value": "£18.2m",
                        "value_numeric": 18.2,
                        "basis": "reported",
                        "source_url": "https://example.com/debt",
                    }
                ],
            }
        ]
    )
    assert "Net debt" in metrics
    assert "£18.2m" in metrics
    assert "Down 24.2% from £24.0m" in metrics
    assert "Reported" in metrics


def test_company_public_kpis_exclude_one_off_narrative_facts() -> None:
    assert not _metric_series_is_displayable(
        {
            "latest_value": "No return expected from any asset sale",
            "points": [{"value": "No return expected from any asset sale"}],
        }
    )
    assert _metric_series_is_displayable(
        {
            "latest_value": "£18.2m",
            "points": [{"value": "£18.2m", "value_numeric": 18.2}],
        }
    )
    assert _metric_series_is_displayable(
        {
            "latest_value": "In line with expectations",
            "points": [
                {"value": "In line with expectations"},
                {"value": "In line with expectations"},
            ],
        }
    )


def test_company_timeline_is_compact_and_hides_other() -> None:
    markup = _timeline_markup(
        {
            "source_id": "gamma",
            "published_at": "2026-08-21T11:00:00+01:00",
            "rns_type": "Other",
            "impact_colour": "amber",
            "impact_level": "high",
            "headline": "Waterland takeover talks disclosed under Rule 2.4",
            "takeaway": "Gamma confirms discussions about a possible offer. No offer price has been disclosed.",
            "source_url": "https://example.com/gamma",
            "price": None,
        }
    )
    assert 'data-company-timeline="row"' in markup
    assert "Formal takeover interest emerges; terms remain unknown" in markup
    assert "HIGH · MIXED" in markup
    assert ">Other<" not in markup
    assert "Original RNS ↗" in markup
    assert "Gamma confirms discussions" not in markup


def test_company_gaps_escape_untrusted_content() -> None:
    markup = _gaps_markup(
        [
            {
                "item": '<script>alert("gap")</script>',
                "source_url": "https://example.com/gap",
            }
        ]
    )
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_company_source_removes_system_count_cards_and_building_banner() -> None:
    source = Path("ui/company.py").read_text(encoding="utf-8")
    for deprecated in (
        "Analysed RNSs",
        "Tracked metrics",
        "Open promises",
        "sca-intel-grid",
        "sca-building",
        "Latest view",
    ):
        assert deprecated not in source
    assert 'data-company-section="current-position"' in source
    assert '"Guidance"' in source
    assert '"Metrics that matter"' in source
    assert '"Management promises"' in source
    assert '"What remains unclear"' in source
    assert '"RNS timeline"' in source


def test_company_sections_are_conditional_and_timeline_is_progressive() -> None:
    source = Path("ui/company.py").read_text(encoding="utf-8")
    assert "if guidance:" in source
    assert "if metrics:" in source
    assert "if open_claims or resolved_claims:" in source
    assert "if gaps:" in source
    assert "announcements[:12]" in source
    assert 'st.expander(f"Earlier announcements · {len(earlier)}"' in source


def test_company_mobile_layout_collapses_metrics() -> None:
    assert ".sca-company-metrics{grid-template-columns:1fr" in COMPANY_CSS
    assert ".sca-company-title{font-size:1.9rem" in COMPANY_CSS
    assert "min-height:2.75rem" in COMPANY_CSS


def test_beta_entrance_has_one_message_one_input_one_action() -> None:
    source = Path("ui/beta.py").read_text(encoding="utf-8")
    assert "Know what changed.<br>See the evidence." in source
    assert "Every AIM announcement analysed in minutes" in source
    assert 'st.text_input("Private beta access code"' in source
    assert '"Enter Smallcaps.ai"' in source
    assert "Read the change" not in source
    assert "See the numbers" not in source
    assert "Check the source" not in source
    assert "sca-beta-points" not in source
    assert "UNLOCK PRIVATE BETA" not in source
    assert "max-width:620px" in BETA_CSS
    assert '[data-testid="stForm"]' in BETA_CSS
    assert '[data-testid="stFormSubmitButton"] button' in BETA_CSS


def test_streamlit_app_uses_new_beta_boundary() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "from ui.beta import require_beta_access" in source
    assert "require_beta_access," not in source
