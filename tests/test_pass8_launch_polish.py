from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


ROOT = Path(__file__).resolve().parents[1]


def test_company_repository_uses_one_isolated_light_asset_stack() -> None:
    html = (ROOT / "frontend" / "company.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "assets" / "company-pass4.css").read_text(
        encoding="utf-8"
    )

    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '<meta name="color-scheme" content="light">' in html
    assert '/assets/news.css' in html
    assert '/assets/watchlist.css' in html
    assert '/assets/company-pass4.css' in html
    assert '/assets/product-shell.css' in html
    assert '/assets/company.js' in html
    assert '/assets/product-shell.js' in html
    for retired in (
        '/assets/research.css',
        '/assets/company.css',
        '/assets/company-polish.css',
        '/assets/company-launch.css',
        '/assets/company-journey.js',
        '/assets/company-launch.js',
    ):
        assert retired not in html

    assert '<p class="eyebrow">Company</p>' in html
    assert "company-repository-page" in html
    assert "Company Intelligence" not in html
    assert 'data-product-nav="news"' in html
    assert 'data-product-nav="watchlist"' in html
    assert 'data-product-nav="daily"' not in html
    assert "data-company-search" in html
    assert 'id="company-context-link"' in html
    assert "COMPANY MONITORING SHEET" not in html

    assert "color-scheme:light" in css
    assert ".company-position-card" in css
    assert ".company-position-snapshot" in css
    assert ".company-matter-card" in css
    assert ".company-event" in css
    assert ".company-watch-toggle" in css and "min-height:44px" in css
    assert "@media (prefers-reduced-motion:reduce)" in css


def test_company_page_renders_existing_evidence_without_report_rewriting() -> None:
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


def test_the_aim_daily_is_not_a_customer_surface_or_home_route(monkeypatch) -> None:
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    for name in (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(Starlette(routes=create_frontend_routes()))

    home = client.get("/")
    assert home.status_code == 200
    assert "AIM COMPANY NEWS" in home.text
    assert "THE AIM DAILY" not in home.text
    assert 'data-product-nav="daily"' not in home.text

    # Historical assets remain until the final migration/cleanup pass, but no
    # customer-facing page links to them.
    assert (ROOT / "frontend" / "daily.html").exists()
    for name in ("index.html", "company.html", "access.html"):
        html = (ROOT / "frontend" / name).read_text(encoding="utf-8")
        assert "The AIM Daily" not in html
        assert 'data-product-nav="daily"' not in html


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
