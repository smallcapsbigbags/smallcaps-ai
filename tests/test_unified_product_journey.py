from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import _safe_next, create_frontend_routes


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_private_beta_preserves_the_exact_dated_feed_destination(monkeypatch) -> None:
    monkeypatch.setenv("PRIVATE_BETA_MODE", "true")
    monkeypatch.setenv("APP_BETA_PASSWORD", "preview-access")
    client = TestClient(Starlette(routes=create_frontend_routes()))
    destination = "/?date=2026-08-21&open=spr-preview-buyback"

    locked = client.get(destination)
    assert locked.status_code == 200
    assert (
        'name="next" value="/?date=2026-08-21&amp;open=spr-preview-buyback"'
        in locked.text
    )

    unlocked = client.post(
        "/access",
        data={"access_code": "preview-access", "next": destination},
        follow_redirects=False,
    )
    assert unlocked.status_code == 303
    assert unlocked.headers["location"] == destination
    assert "httponly" in unlocked.headers["set-cookie"].lower()


def test_private_beta_rejects_an_external_or_header_injection_destination(monkeypatch) -> None:
    assert _safe_next("//example.com/steal") == "/"
    assert _safe_next("/\r\nX-Injected: yes") == "/"

    monkeypatch.setenv("PRIVATE_BETA_MODE", "true")
    monkeypatch.setenv("APP_BETA_PASSWORD", "preview-access")
    client = TestClient(Starlette(routes=create_frontend_routes()))
    response = client.post(
        "/access",
        data={"access_code": "preview-access", "next": "//example.com/steal"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_feed_owns_company_data_links_and_shareable_company_news_state() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    javascript = (ASSETS / "research.js").read_text(encoding="utf-8")

    assert "/assets/feed-company.js" not in html
    assert "URLSearchParams" in javascript
    assert 'params.get("date")' in javascript
    assert 'params.get("open")' in javascript
    assert "writeJourneyUrl" in javascript
    assert "history.replaceState" in javascript
    assert "company-research-link" in javascript
    assert "company-inline-link" in javascript
    assert "scbb-monitoring-v1" in javascript
    assert "KEY_NEWS_THRESHOLD = 3" in javascript
    assert 'id="search-filter"' in html
    assert "data-company-search-input" in html


def test_company_repository_builds_exact_dated_news_links_and_inline_detail() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")
    javascript = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    assert "/assets/company-repo.js" in html
    assert "/assets/company.js" not in html
    assert "/assets/company-journey.js" not in html
    assert "/assets/company-launch.js" not in html
    assert "function newsHref" in javascript
    assert 'params.set("date", dateValue)' in javascript
    assert 'params.set("open", clean(sourceId))' in javascript
    assert 'return query ? `/rns?${query}` : "/rns";' in javascript
    assert "details.dataset.sourceId" in javascript
    assert "new URLSearchParams(window.location.search)" in javascript
    assert 'element("details", `repo-news-item' in javascript
    assert "loadEventDetail" in javascript
    assert "activateRequestedAnnouncement" in javascript
    assert "innerHTML" not in javascript


def test_shared_shell_preserves_source_context_without_arbitrary_return_urls() -> None:
    shell = (ASSETS / "product-shell.js").read_text(encoding="utf-8")

    assert 'const COMPANY_CONTEXTS = new Set(["news", "watchlist"])' in shell
    assert 'url.searchParams.set("from", surface)' in shell
    assert 'url.searchParams.set("open", sourceId)' in shell
    assert 'new URLSearchParams({ watchlist: "1" })' in shell
    assert 'return COMPANY_CONTEXTS.has(value) ? value : "news"' in shell
    assert "daily_state" not in shell
    assert "daily_date" not in shell
    assert "return_url" not in shell
    assert "next_url" not in shell
    assert "fetch(" not in shell


def test_mobile_product_headers_and_company_repository_share_one_layout() -> None:
    feed = (FRONTEND / "index.html").read_text(encoding="utf-8")
    company = (FRONTEND / "company.html").read_text(encoding="utf-8")
    company_css = (ASSETS / "company-repo.css").read_text(encoding="utf-8")
    shell_css = (ASSETS / "product-shell.css").read_text(encoding="utf-8")
    compact = "".join(shell_css.split())

    for html in (feed, company):
        assert 'button class="text-action" type="submit">Sign out</button>' in html
        assert "product-page" in html
        assert 'data-product-status>AIM live</span>' in html
        assert '/assets/product-shell.css?v={{ASSET_VERSION}}' in html
        assert "data-company-search" in html
        assert 'data-product-nav="daily"' not in html

    assert ".company-watch-toggle" in company_css
    assert ".repo-story-grid" in company_css
    assert ".repo-metric-grid" in company_css
    assert ".repo-news-summary" in company_css
    assert ".repo-detail-grid" in company_css
    assert "@media (max-width: 680px)" in company_css
    assert 'grid-template-areas:"brandmeta""navnav""searchsearch"' in compact
    assert ".product-page .company-search" in shell_css
    assert ".product-page .live-status" in shell_css
    assert "min-height:44px" in compact
