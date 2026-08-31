from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_the_aim_daily_uses_the_shared_light_product_shell() -> None:
    html = (ROOT / "frontend" / "daily.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "assets" / "daily.css").read_text(encoding="utf-8")

    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert html.index('/assets/research.css') < html.index('/assets/news.css')
    assert html.index('/assets/news.css') < html.index('/assets/daily.css')
    assert 'class="header-inner"' in html
    assert 'class="primary-nav"' in html
    assert 'class="nav-link nav-link-active" href="/"' in html
    assert 'href="/rns">News</a>' in html
    assert 'href="/rns?watchlist=1">Watchlist</a>' in html
    assert '>The AIM Daily</a>' in html
    assert "AIM live" in html

    for retired_dark_token in ("#03080d", "#46d7ff", "rgb(3, 8, 13)"):
        assert retired_dark_token not in html
        assert retired_dark_token not in css

    assert "width:min(var(--content),calc(100% - 40px))" in css
    assert "background:var(--page)" in css
    assert "background:var(--surface)" in css
    assert "color:var(--blue)" in css
    assert "border-radius:var(--daily-card-radius)" in css
    assert ".daily-summary-strip" in css
    assert ".lead-layout" in css
    assert ".also-story" in css
    assert ".quick-list" in css
    assert "min-height:48px" in css
    assert "@media (prefers-reduced-motion:reduce)" in css


def test_the_aim_daily_retains_its_editorial_and_runtime_contract() -> None:
    html = (ROOT / "frontend" / "daily.html").read_text(encoding="utf-8")
    javascript = (ROOT / "frontend" / "assets" / "daily.js").read_text(
        encoding="utf-8"
    )

    for required_id in (
        'id="daily-edition"',
        'id="daily-title"',
        'id="edition-summary"',
        'id="lead-section"',
        'id="lead-story"',
        'id="also-section"',
        'id="also-stories"',
        'id="quick-section"',
        'id="quick-stories"',
        'id="rest-summary"',
        'id="daily-error"',
    ):
        assert required_id in html

    for editorial_label in (
        "THE AIM DAILY",
        "THE LEAD",
        "ALSO THIS MORNING",
        "QUICK TAKES",
        "THE REST OF AIM",
    ):
        assert editorial_label in html

    assert "aim-daily-newsroom-v1" in javascript
    assert "/api/v1/aim-daily/newsroom" in javascript
    assert 'params.get("date")' in javascript
    assert "renderLead" in javascript
    assert "renderAlso" in javascript
    assert "renderQuick" in javascript
    assert "innerHTML" not in javascript
