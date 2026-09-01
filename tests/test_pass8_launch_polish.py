from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_company_intelligence_uses_one_isolated_light_asset_stack() -> None:
    html = (ROOT / "frontend" / "company.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "assets" / "company-pass4.css").read_text(
        encoding="utf-8"
    )

    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '<meta name="color-scheme" content="light">' in html
    assert '/assets/news.css' in html
    assert '/assets/watchlist.css' in html
    assert '/assets/company-pass4.css' in html
    assert '/assets/company.js' in html
    for retired in (
        '/assets/research.css',
        '/assets/company.css',
        '/assets/company-polish.css',
        '/assets/company-launch.css',
        '/assets/company-journey.js',
        '/assets/company-launch.js',
    ):
        assert retired not in html

    assert "COMPANY INTELLIGENCE" in html.upper()
    assert 'href="/rns">News</a>' in html
    assert 'href="/rns?watchlist=1">Watchlist' in html
    assert 'href="/">The AIM Daily</a>' in html
    assert "COMPANY MONITORING SHEET" not in html

    assert "color-scheme:light" in css
    assert ".company-position-card" in css
    assert ".company-position-snapshot" in css
    assert ".company-matter-card" in css
    assert ".company-event" in css
    assert ".company-watch-toggle" in css and "min-height:44px" in css
    assert "@media (prefers-reduced-motion:reduce)" in css


def test_company_page_renders_final_language_directly_without_dom_rewriting() -> None:
    javascript = (ROOT / "frontend" / "assets" / "company.js").read_text(
        encoding="utf-8"
    )

    for required in (
        '"Current position"',
        '"What matters now"',
        '"Evidence trail"',
        '"What changed"',
        '"Smallcaps.ai view"',
        '"Show supporting evidence"',
        '"Reported facts"',
        '"Before → now"',
        '"Not disclosed / source checks"',
        '"Open in News →"',
        '"Source RNS ↗"',
    ):
        assert required in javascript

    for retired_visible_copy in (
        '"CURRENT VIEW"',
        '"LATEST COMPANY NEWS"',
        '"AI VIEW"',
        '"WHAT TO WATCH"',
        '"SUPPORTS THE CASE"',
        '"CHALLENGES THE CASE"',
        '"VIEW FULL ANALYST NOTE"',
    ):
        assert retired_visible_copy not in javascript

    assert "innerHTML" not in javascript
    assert "OpenAI" not in javascript


def test_company_to_news_links_use_the_canonical_company_news_route() -> None:
    javascript = (ROOT / "frontend" / "assets" / "company.js").read_text(
        encoding="utf-8"
    )
    assert "function newsHref" in javascript
    assert 'params.set("date", dateValue)' in javascript
    assert 'params.set("open", clean(sourceId))' in javascript
    assert 'return query ? `/rns?${query}` : "/rns";' in javascript
    assert 'return query ? `/?${query}`' not in javascript


def test_the_aim_daily_keeps_its_editorial_identity_inside_the_product_shell() -> None:
    html = (ROOT / "frontend" / "daily.html").read_text(encoding="utf-8")

    assert "THE AIM DAILY" in html
    assert "Preparing edition" in html
    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '/assets/news.css' in html
    assert 'class="header-inner"' in html
    assert 'href="/rns">News</a>' in html
    assert 'href="/rns?watchlist=1">Watchlist</a>' in html
    assert 'href="/" aria-current="page">The AIM Daily</a>' in html
    assert "AIM live" in html
    assert "VIEW ALL COMPANY NEWS →" in html
    assert "OPEN COMPANY NEWS →" in html
    assert "RNS MONITOR" not in html
    assert "OPEN RNS MONITOR" not in html


def test_company_pass4_is_presentation_not_a_new_ai_or_database_feature() -> None:
    company_javascript = (
        ROOT / "frontend" / "assets" / "company.js"
    ).read_text(encoding="utf-8")
    company_html = (ROOT / "frontend" / "company.html").read_text(encoding="utf-8")

    assert company_javascript.count("/api/v1/company/") == 1
    assert "database" not in company_javascript.lower()
    assert "OPENAI" not in company_javascript.upper()
    assert "company-pass4.css" in company_html
    assert "company-launch.js" not in company_html
