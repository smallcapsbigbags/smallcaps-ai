from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import _safe_next, create_frontend_routes


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


def test_feed_owns_company_navigation_and_shareable_company_news_state() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/research.js").read_text(encoding="utf-8")

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


def test_company_history_builds_exact_dated_feed_links_and_table_semantics() -> None:
    html = Path("frontend/company.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/company-journey.js").read_text(encoding="utf-8")

    assert "/assets/company-journey.js" in html
    assert "company-feed-link" in javascript
    assert "data-source-id" not in javascript
    assert "row.dataset.sourceId" in javascript
    assert "parseDisplayDate" in javascript
    assert 'setAttribute("role", "table")' in javascript
    assert "innerHTML" not in javascript


def test_mobile_product_headers_retain_sign_out_and_responsive_status() -> None:
    feed = Path("frontend/index.html").read_text(encoding="utf-8")
    company = Path("frontend/company.html").read_text(encoding="utf-8")
    shared_css = Path("frontend/assets/company-polish.css").read_text(encoding="utf-8")
    news_css = Path("frontend/assets/news.css").read_text(encoding="utf-8")

    assert 'button class="text-action" type="submit">Sign out</button>' in feed
    assert "status-full" in company and "status-compact" in company
    assert "display: inline-flex" in shared_css
    assert ".text-action" in shared_css
    assert ".status-compact" in shared_css
    assert "@media (max-width: 680px)" in news_css
    assert ".live-status { display: none; }" in news_css
