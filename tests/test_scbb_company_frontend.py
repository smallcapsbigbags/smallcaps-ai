from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


def test_company_frontend_uses_the_pass4_investor_decision_contract() -> None:
    html = Path("frontend/company.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/company.js").read_text(encoding="utf-8")
    css = Path("frontend/assets/company-pass4.css").read_text(encoding="utf-8")

    assert "COMPANY INTELLIGENCE" in html.upper()
    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '<meta name="color-scheme" content="light">' in html
    for asset in (
        "news.css",
        "watchlist.css",
        "company-pass4.css",
        "watchlist.js",
        "company-watchlist.js",
        "company.js",
    ):
        assert asset in html
    for retired_asset in (
        "research.css",
        "company.css",
        "company-polish.css",
        "company-launch.css",
        "company-journey.js",
        "company-launch.js",
    ):
        assert retired_asset not in html

    assert 'href="/rns">News</a>' in html
    assert 'href="/rns?watchlist=1">Watchlist' in html
    assert 'href="/">The AIM Daily</a>' in html
    assert "Current position. What matters now. Source-linked evidence." in html
    assert "COMPANY MONITORING SHEET" not in html

    assert 'const COMPANY_SCHEMA = "scbb-company-v1"' in javascript
    assert 'const MONITORING_SCHEMA = "scbb-monitoring-v1"' in javascript
    assert '"Current position"' in javascript
    assert '"What matters now"' in javascript
    assert '"Evidence trail"' in javascript
    assert '"current-position"' in javascript
    assert '"what-matters"' in javascript
    assert '"evidence-trail"' in javascript
    assert '"What changed"' in javascript
    assert '"Smallcaps.ai view"' in javascript
    assert '"Show supporting evidence"' in javascript
    assert '"Open in News →"' in javascript
    assert '"Source RNS ↗"' in javascript
    assert "INITIAL_HISTORY_COUNT = 8" in javascript
    assert "history.replaceState" not in javascript
    assert "innerHTML" not in javascript
    assert "OpenAI" not in javascript

    for retired_visible_copy in (
        '"CURRENT VIEW"',
        '"LATEST COMPANY NEWS"',
        '"AI VIEW"',
        '"RNS HISTORY"',
        '"VIEW FULL ANALYST NOTE"',
        '"READ ANALYSIS →"',
    ):
        assert retired_visible_copy not in javascript

    assert "color-scheme: light" in css
    assert ".company-position-card" in css
    assert ".company-position-main" in css
    assert ".company-position-snapshot" in css
    assert ".company-matters-grid" in css
    assert ".company-matter-card" in css
    assert ".company-event" in css
    assert ".company-evidence-grid" in css
    assert "min-height:44px" in css
    assert "@media (max-width:680px)" in css
    assert "@media (prefers-reduced-motion:reduce)" in css


def test_private_beta_preserves_the_requested_company_destination(monkeypatch) -> None:
    monkeypatch.setenv("PRIVATE_BETA_MODE", "true")
    monkeypatch.setenv("APP_BETA_PASSWORD", "preview-access")
    app = Starlette(routes=create_frontend_routes())
    client = TestClient(app)

    locked = client.get("/company/SPR?open=spr-preview-buyback")
    assert locked.status_code == 200
    assert (
        'name="next" value="/company/SPR?open=spr-preview-buyback"'
        in locked.text
    )
    assert "PRIVATE BETA ACCESS" in locked.text

    destination = "/company/SPR?open=spr-preview-buyback"
    unlocked = client.post(
        "/access",
        data={"access_code": "preview-access", "next": destination},
        follow_redirects=False,
    )
    assert unlocked.status_code == 303
    assert unlocked.headers["location"] == destination
    assert "httponly" in unlocked.headers["set-cookie"].lower()


def test_feed_builds_company_navigation_without_a_mutation_enhancer() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/research.js").read_text(encoding="utf-8")

    assert "/assets/company.css" not in html
    assert "/assets/company-polish.css" not in html
    assert "/assets/news-pass3.css" in html
    assert "/assets/news-pass3-polish.css" in html
    assert "/assets/feed-company.js" not in html
    assert "company-research-link" in javascript
    assert "company-inline-link" in javascript
