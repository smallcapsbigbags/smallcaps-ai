from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_the_aim_daily_uses_the_shared_light_product_shell() -> None:
    html = (ROOT / "frontend" / "daily.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "assets" / "daily.css").read_text(encoding="utf-8")
    shell = (ROOT / "frontend" / "assets" / "product-shell.css").read_text(
        encoding="utf-8"
    )
    compact_css = "".join(css.split())
    compact_shell = "".join(shell.split())

    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '<meta name="color-scheme" content="light">' in html
    assert '/assets/research.css' not in html
    assert html.index('/assets/news.css') < html.index('/assets/daily.css')
    assert html.index('/assets/daily.css') < html.index('/assets/product-shell.css')
    assert 'class="header-inner"' in html
    assert 'class="primary-nav"' in html
    assert 'data-product-nav="daily"' in html
    assert 'data-product-nav="news"' in html
    assert 'data-product-nav="watchlist"' in html
    assert "AIM live" in html
    assert '/assets/watchlist.js?v={{ASSET_VERSION}}' in html
    assert '/assets/product-shell.js?v={{ASSET_VERSION}}' in html

    for retired_dark_token in ("#03080d", "#46d7ff", "rgb(3, 8, 13)"):
        assert retired_dark_token not in html
        assert retired_dark_token not in css

    assert "width:min(var(--content),calc(100%-40px))" in compact_css
    assert "background:var(--page)" in compact_css
    assert "background:var(--surface)" in compact_css
    assert "color:var(--blue)" in compact_css
    assert "border-radius:var(--daily-card-radius)" in compact_css
    assert ".daily-summary-strip" in css
    assert ".lead-layout" in css
    assert ".also-story" in css
    assert ".quick-list" in css
    assert "min-height:48px" in compact_css
    assert "@media(prefers-reduced-motion:reduce)" in compact_css

    assert ".product-page .header-inner" in shell
    assert 'grid-template-areas:"brandmeta""navnav"' in compact_shell
    assert ".product-page .product-footer-links" in shell
    assert "min-height:44px" in compact_shell


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
