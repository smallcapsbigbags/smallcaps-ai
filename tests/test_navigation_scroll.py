from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_routes_reset_scroll_when_destination_changes() -> None:
    app = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    helper = (ROOT / "ui" / "navigation_scroll.py").read_text(encoding="utf-8")

    assert "from ui.navigation_scroll import reset_scroll_on_view_change" in app
    assert "reset_scroll_on_view_change(" in app
    assert 'source_id=query_value("source_id")' in app
    assert 'ticker=query_value("ticker")' in app

    assert "_smallcaps_last_view_signature" in helper
    assert "st.iframe(" in helper
    assert "st.components.v1.html" not in helper
    assert "MutationObserver" in helper
    assert "ResizeObserver" in helper
    assert "holdForMs = 2400" in helper
    assert "p.document.querySelector('[data-testid=\"stMain\"]')" in helper
    assert "el.scrollTop = 0" in helper
    assert "p.setInterval" in helper
    assert "p.requestAnimationFrame" in helper


def test_scroll_reset_does_not_run_for_same_logical_destination() -> None:
    helper = (ROOT / "ui" / "navigation_scroll.py").read_text(encoding="utf-8")

    assert "signature = \"|\".join" in helper
    assert "if st.session_state.get(_LAST_VIEW_SIGNATURE) == signature:" in helper
    assert "st.session_state[_LAST_VIEW_SIGNATURE] = signature" in helper
