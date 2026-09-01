from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_company_repository_uses_one_isolated_light_asset_stack() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")
    css = (ASSETS / "company-repo.css").read_text(encoding="utf-8")

    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '<meta name="color-scheme" content="light">' in html
    for asset in (
        "/assets/news.css",
        "/assets/watchlist.css",
        "/assets/product-shell.css",
        "/assets/company-repo.css",
        "/assets/company-repo.js",
        "/assets/product-shell.js",
    ):
        assert asset in html

    for retired in (
        "/assets/research.css",
        "/assets/company.css",
        "/assets/company-polish.css",
        "/assets/company-pass4.css",
        "/assets/company-launch.css",
        "/assets/company.js",
        "/assets/company-journey.js",
        "/assets/company-launch.js",
        "/assets/investor-workflow.css",
        "/assets/investor-workflow.js",
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

    assert ".repo-story" in css
    assert ".repo-story-grid" in css
    assert ".repo-metric-grid" in css
    assert ".repo-news-list" in css
    assert ".repo-news-item" in css
    assert ".repo-detail-grid" in css
    assert ".company-watch-toggle" in css
    assert "min-height: 44px" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_company_page_renders_existing_facts_as_a_running_repository() -> None:
    javascript = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    for required in (
        'storyCell("NOW"',
        'storyCell("CHANGE"',
        'storyCell("WATCH"',
        'sectionHead("Key numbers"',
        'sectionHead("Company news"',
        'detailGroup("FACTS")',
        'detailGroup("CHANGE")',
        'detailGroup("WATCH")',
        '"NOT DISCLOSED"',
        '"Open in News →"',
        '"Source ↗"',
    ):
        assert required in javascript

    for retired_visible_copy in (
        '"Current position"',
        '"What matters now"',
        '"Evidence trail"',
        '"Smallcaps.ai view"',
        '"Show supporting evidence"',
        '"SUPPORTS THE CASE"',
        '"CHALLENGES THE CASE"',
        '"VIEW FULL ANALYST NOTE"',
    ):
        assert retired_visible_copy not in javascript

    assert "innerHTML" not in javascript
    assert "OpenAI" not in javascript


def test_company_to_news_links_use_the_canonical_company_news_route() -> None:
    javascript = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

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
    assert (FRONTEND / "daily.html").exists()
    for name in ("index.html", "company.html", "access.html"):
        html = (FRONTEND / name).read_text(encoding="utf-8")
        assert "The AIM Daily" not in html
        assert 'data-product-nav="daily"' not in html


def test_company_repo_is_presentation_not_a_new_ai_or_database_feature() -> None:
    javascript = (ASSETS / "company-repo.js").read_text(encoding="utf-8")
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")

    assert javascript.count("/api/v1/company/") == 1
    assert javascript.count("fetch(") == 2
    assert "database" not in javascript.lower()
    assert "OPENAI" not in javascript.upper()
    assert "XMLHttpRequest" not in javascript
    assert "WebSocket" not in javascript
    assert "company-repo.css" in html
    assert "company-repo.js" in html
    assert "company-pass4.css" not in html
    assert "/assets/company.js" not in html
