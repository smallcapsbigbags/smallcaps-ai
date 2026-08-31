from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


def test_company_frontend_uses_the_launch_visual_and_research_contract() -> None:
    html = Path("frontend/company.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/company.js").read_text(encoding="utf-8")
    journey = Path("frontend/assets/company-journey.js").read_text(encoding="utf-8")
    launch = Path("frontend/assets/company-launch.js").read_text(encoding="utf-8")
    launch_css = Path("frontend/assets/company-launch.css").read_text(encoding="utf-8")

    assert "COMPANY INTELLIGENCE" in html
    assert '<meta name="theme-color" content="#f5f6f8">' in html
    for asset in (
        "news.css",
        "company.css",
        "company-polish.css",
        "company-launch.css",
        "watchlist.js",
        "company-watchlist.js",
        "company.js",
        "company-journey.js",
        "company-launch.js",
    ):
        assert asset in html
    assert 'href="/rns">News</a>' in html
    assert 'href="/rns?watchlist=1">Watchlist' in html
    assert 'href="/">The AIM Daily</a>' in html
    assert "COMPANY MONITORING SHEET" not in html

    # The existing company read model remains the data source; Pass 8 changes
    # presentation and vocabulary deterministically without another API/model call.
    assert "scbb-company-v1" in javascript
    assert "innerHTML" not in javascript
    assert "innerHTML" not in journey
    assert "company-feed-link" in journey
    assert 'link.href = `/rns?date=${isoDate}&open=${encodeURIComponent(sourceId)}`;' in journey
    assert 'link.textContent = "OPEN IN NEWS →";' in journey

    for mapping in (
        '"CURRENT VIEW": "LATEST COMPANY NEWS"',
        '"MANAGEMENT PROMISES": "MANAGEMENT COMMITMENTS"',
        '"RNS HISTORY": "COMPANY NEWS HISTORY"',
        'setText(label, "TAKE")',
        'setText(detailsSummary, "VIEW EVIDENCE")',
        'setText(heading, "MATERIAL FACTS")',
        'setText(heading, "NOT DISCLOSED / SOURCE CHECKS")',
    ):
        assert mapping in launch
    assert "fetch(" not in launch

    assert "color-scheme: light" in launch_css
    assert "--page: #f5f6f8" in launch_css
    assert "--panel: #ffffff" in launch_css
    assert "--blue: #2563eb" in launch_css
    assert "font-size: clamp(42px, 5.2vw, 64px)" in launch_css
    assert ".company-watch-toggle" in launch_css
    assert "min-height: 44px" in launch_css
    assert "@media (prefers-reduced-motion: reduce)" in launch_css


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

    assert "/assets/company.css" in html
    assert "/assets/company-polish.css" in html
    assert "/assets/feed-company.js" not in html
    assert "company-research-link" in javascript
    assert "company-inline-link" in javascript
