import inspect
from pathlib import Path

from ui.note import _change_markup, _evidence_markup, _list_markup, _render_executive_layer
from ui.note_styles import NOTE_CSS


def _facts():
    return [
        {
            "label": "Notice of intention to appoint administrators",
            "value": "Filed",
            "previous_value": "No administration notice disclosed",
            "basis": "reported",
        },
        {
            "label": "Going concern funding position",
            "value": "Insufficient funds to continue as a going concern",
            "comparator": "Not disclosed in supplied prior context",
            "basis": "reported",
        },
        {
            "label": "Potential shareholder recovery",
            "value": "No return expected from any asset sale",
            "basis": "reported",
        },
    ]


def test_note_executive_evidence_is_edited_and_source_led() -> None:
    markup = _evidence_markup(_facts())

    assert "Evidence from the RNS" in markup
    assert ">Administration<" in markup
    assert "Notice of intention filed" in markup
    assert ">Funding position<" in markup
    assert ">Shareholder recovery<" in markup
    assert "No administration notice disclosed" not in markup
    assert "Not disclosed in supplied prior context" not in markup
    assert "Reported" not in markup


def test_note_executive_evidence_marks_calculations_without_repeating_reported() -> None:
    markup = _evidence_markup(
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

    assert "Previous: £24.0m" in markup
    assert markup.count("Smallcaps.ai calculation") == 1
    assert markup.count("sca-note-evidence-value-num") == 2


def test_note_empty_sections_render_nothing() -> None:
    assert _list_markup([]) == ""
    assert _list_markup(["", "  "]) == ""
    assert _change_markup({}) == ""
    assert _change_markup({"before": "", "today": "", "read_through": ""}) == ""


def test_note_change_detail_only_shows_supported_values() -> None:
    markup = _change_markup(
        {
            "before": "Net debt was £24.0m.",
            "today": "Net debt is £18.2m.",
            "read_through": "Balance-sheet risk has reduced.",
        }
    )
    assert "Before" in markup
    assert "Today" in markup
    assert "Why it matters" in markup
    assert "£24.0m" in markup
    assert "£18.2m" in markup


def test_note_source_uses_executive_hierarchy_and_progressive_disclosure() -> None:
    executive = inspect.getsource(_render_executive_layer)
    markers = [
        'data-note-section="what-happened"',
        "_evidence_markup",
        'data-note-section="our-view"',
        'data-note-section="what-to-watch"',
        "Supporting detail",
    ]
    positions = [executive.index(marker) for marker in markers]
    assert positions == sorted(positions)

    source = Path("ui/note.py").read_text(encoding="utf-8")
    assert 'st.expander("What changed"' in source
    assert 'st.expander("Full evidence & calculations"' in source
    assert 'st.expander("Investment case detail"' in source
    assert 'st.expander("Disclosure & terminology"' in source
    assert 'st.expander("Market reaction"' in source


def test_note_removes_generated_empty_state_copy_and_duplicate_bottom_actions() -> None:
    source = Path("ui/note.py").read_text(encoding="utf-8")

    assert "No new supporting evidence identified." not in source
    assert "No new challenge identified." not in source
    assert "No genuine guidance change identified." not in source
    assert "No specific watch item identified." not in source
    assert "Market reaction will appear once" not in source
    assert 'st.button("Company →"' not in source


def test_note_keeps_quiet_direct_source_navigation() -> None:
    source = Path("ui/note.py").read_text(encoding="utf-8")
    assert '"← Feed"' in source
    assert '"Company"' in source
    assert '"Original RNS ↗"' in source
    assert "st-key-note-nav" in NOTE_CSS


def test_note_mobile_design_collapses_evidence_and_detail_to_one_column() -> None:
    assert ".sca-note-evidence-grid{grid-template-columns:1fr" in NOTE_CSS
    assert ".sca-note-detail-grid{grid-template-columns:1fr" in NOTE_CSS
    assert "min-height:2.55rem" in NOTE_CSS
