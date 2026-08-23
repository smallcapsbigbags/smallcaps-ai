from pathlib import Path


def test_internal_navigation_resets_retained_scroll_position() -> None:
    common = Path("ui/common.py").read_text(encoding="utf-8")

    assert "def consume_scroll_to_top" in common
    assert "st.session_state[_SCROLL_FLAG] = True" in common
    assert "consume_scroll_to_top()" in common.split("def inject_styles", 1)[1]
    assert "p.scrollTo(0, 0)" in common
    assert "stAppViewContainer" in common
    assert "stMain" in common
    assert "history.scrollRestoration = 'manual'" in common
    assert "frame < 16" in common
    assert "450" in common
    assert "st.iframe(" in common
    assert "tab_index=-1" in common
    assert "streamlit.components.v1" not in common
    assert "components.html(" not in common


def test_mobile_responsive_tables_wrap_instead_of_clipping() -> None:
    common = Path("ui/common.py").read_text(encoding="utf-8")

    assert ".sca-table:not(.sca-table-responsive){min-width:620px}" in common
    assert ".sca-table.sca-table-responsive{min-width:0" in common
    assert "overflow-wrap:anywhere" in common
