from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_feed_uses_facts_no_fluff_company_news_language() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "AIM COMPANY NEWS" in html
    assert "Facts. No fluff." in html
    assert "What changed across AIM." in html
    assert 'id="filter-panel"' in html and 'hidden' in html
    assert '/assets/news.css' in html
    assert '/assets/news-detail.css' in html
    assert "COMPANY / RNS / SIGNAL" not in html
    assert "AI VIEW" not in html
    assert "GROUP BY COMPANY" not in html
    assert "ANALYST MONITORING SHEET" not in html


def test_feed_visual_system_is_light_dense_and_signal_separated() -> None:
    css = (ROOT / "frontend" / "assets" / "news.css").read_text(
        encoding="utf-8"
    )
    shared = (ROOT / "frontend" / "assets" / "research.css").read_text(
        encoding="utf-8"
    )
    assert "color-scheme: light" in css
    assert "--page: #f5f6f8" in css
    assert "--surface: #ffffff" in css
    assert "--blue: #2563eb" in css
    assert '.monitor-row[data-signal="GREEN"]' in css
    assert '.monitor-row[data-signal="AMBER"]' in css
    assert '.monitor-row[data-signal="RED"]' in css
    assert ".impact-dot.filled" in css
    assert "border-radius: 9px" in css
    assert "color-scheme: dark" in shared
    assert "--cyan: #46d7ff" in shared


def test_key_news_and_take_limits_are_code_locked() -> None:
    js = (ROOT / "frontend" / "assets" / "research.js").read_text(
        encoding="utf-8"
    )
    assert "const KEY_NEWS_THRESHOLD = 3;" in js
    assert 'GREEN: "Positive"' in js
    assert 'AMBER: "Mixed"' in js
    assert 'RED: "Negative"' in js
    assert '"NO COLOUR": "Neutral"' in js
    assert "compactWords(row.takeaway || row.ai_view || row.what_changed, 45)" in js
    assert "Show key news only" in js
    assert "other update" in js
    assert "PRICE PENDING" in js


def test_private_beta_matches_company_news_brand_language() -> None:
    html = (ROOT / "frontend" / "access.html").read_text(encoding="utf-8")
    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '/assets/news.css' in html
    assert "AIM COMPANY NEWS" in html
    assert "Facts" in html and "No fluff" in html
    assert "Every material AIM announcement reduced to the facts" in html
    assert '<span class="status-full">PRIVATE BETA</span>' in html
