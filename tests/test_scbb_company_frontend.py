from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_company_frontend_uses_the_compact_repository_contract() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")
    javascript = (ASSETS / "company-repo.js").read_text(encoding="utf-8")
    css = (ASSETS / "company-repo.css").read_text(encoding="utf-8")

    assert '<p class="eyebrow">Company</p>' in html
    assert "company-repository-page" in html
    assert "Company Intelligence" not in html
    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '<meta name="color-scheme" content="light">' in html

    for asset in (
        "news.css",
        "watchlist.css",
        "product-shell.css",
        "company-repo.css",
        "watchlist.js",
        "company-watchlist.js",
        "company-repo.js",
        "product-shell.js",
    ):
        assert f"/assets/{asset}" in html

    for retired_asset in (
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
        assert retired_asset not in html

    assert 'data-product-nav="news"' in html
    assert 'data-product-nav="watchlist"' in html
    assert 'data-product-nav="daily"' not in html
    assert "data-company-search" in html
    assert 'id="company-context-link"' in html
    assert "Independent AIM research. Facts first." in html
    assert "The AIM Daily" not in html

    assert 'const COMPANY_SCHEMA = "scbb-company-v1"' in javascript
    assert 'const MONITORING_SCHEMA = "scbb-monitoring-v1"' in javascript
    assert 'storyCell("NOW"' in javascript
    assert 'storyCell("CHANGE"' in javascript
    assert 'storyCell("WATCH"' in javascript
    assert 'sectionHead("Key numbers"' in javascript
    assert 'sectionHead("Company news"' in javascript
    assert 'detailGroup("FACTS")' in javascript
    assert 'detailGroup("CHANGE")' in javascript
    assert 'detailGroup("WATCH")' in javascript
    assert '"NOT DISCLOSED"' in javascript
    assert '"Open in News →"' in javascript
    assert '"Source ↗"' in javascript
    assert "INITIAL_NEWS_COUNT = 10" in javascript
    assert "MAX_KEY_NUMBERS = 6" in javascript
    assert "activateRequestedAnnouncement" in javascript
    assert 'element("details", `repo-news-item' in javascript
    assert "innerHTML" not in javascript
    assert "OpenAI" not in javascript

    for retired_visible_copy in (
        '"Current position"',
        '"What matters now"',
        '"Evidence trail"',
        '"Smallcaps.ai view"',
        '"Show supporting evidence"',
        '"LATEST COMPANY NEWS"',
        '"RNS HISTORY"',
        '"VIEW FULL ANALYST NOTE"',
    ):
        assert retired_visible_copy not in javascript

    assert ".repo-story-grid" in css
    assert ".repo-story-now" in css
    assert ".repo-story-change" in css
    assert ".repo-story-watch" in css
    assert ".repo-metric-grid" in css
    assert ".repo-news-list" in css
    assert ".repo-news-summary" in css
    assert ".repo-detail-grid" in css
    assert ".company-watch-toggle" in css
    assert "min-height: 44px" in css
    assert "@media (max-width: 680px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


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


def test_feed_renderer_and_shared_shell_have_separate_navigation_responsibilities() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    research = (ASSETS / "research.js").read_text(encoding="utf-8")
    shell = (ASSETS / "product-shell.js").read_text(encoding="utf-8")

    assert "/assets/company.css" not in html
    assert "/assets/company-polish.css" not in html
    assert "/assets/news-pass3.css" in html
    assert "/assets/news-pass3-polish.css" in html
    assert "/assets/feed-company.js" not in html
    assert "company-research-link" in research
    assert "company-inline-link" in research
    assert 'url.searchParams.set("from", surface)' in shell
    assert 'url.searchParams.set("open", sourceId)' in shell
    assert "initialiseCompanySearch" in shell
    assert "fetch(" not in shell
