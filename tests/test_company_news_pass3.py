from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_company_news_uses_an_isolated_light_asset_stack() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert '<meta name="color-scheme" content="light">' in html
    assert '<body class="company-news-page">' in html
    assert 'role="search"' in html
    assert 'class="search-shortcut"' in html

    for legacy_asset in (
        "/assets/research.css",
        "/assets/company.css",
        "/assets/company-polish.css",
    ):
        assert legacy_asset not in html

    assert html.index("/assets/news.css") < html.index("/assets/news-pass3.css")
    assert html.index("/assets/research.js") < html.index("/assets/news-pass3.js")
    assert "/assets/news-pass3.css?v={{ASSET_VERSION}}" in html
    assert "/assets/news-pass3.js?v={{ASSET_VERSION}}" in html


def test_company_news_pass3_resets_rows_and_keeps_them_dense() -> None:
    css = (ROOT / "frontend" / "assets" / "news-pass3.css").read_text(
        encoding="utf-8"
    )
    compact = "".join(css.split())

    for retired_dark_token in ("#03080d", "#07111a", "#46d7ff", "rgb(3,8,13)"):
        assert retired_dark_token not in compact

    assert ".company-news-page.monitor-row" not in compact
    assert ".company-news-page.monitor-row" not in css
    assert ".company-news-page .monitor-row" in css
    assert ".company-news-page .row-toggle" in css
    assert "position:static" in compact
    assert "background:var(--surface)" in compact
    assert "text-align:left" in compact
    assert "-webkit-line-clamp:1" in compact
    assert ".company-news-page .expanded-research" in css
    assert "background:#fbfcfd" in compact
    assert "grid-template-areas:\"brandmeta\"\"navnav\"" in compact
    assert "min-height:44px" in compact
    assert "@media(prefers-reduced-motion:reduce)" in compact


def test_company_news_pass3_adds_no_data_or_ai_call() -> None:
    javascript = (ROOT / "frontend" / "assets" / "news-pass3.js").read_text(
        encoding="utf-8"
    )

    assert "MutationObserver" in javascript
    assert 'closest(".monitor-row")' in javascript
    assert 'row.querySelector(".row-toggle")?.click()' in javascript
    assert 'event.key === "/"' in javascript
    assert 'event.key !== "Escape"' in javascript
    assert "aria-keyshortcuts" in javascript

    for forbidden in ("fetch(", "/api/", "OpenAI", "XMLHttpRequest"):
        assert forbidden not in javascript
