from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


def test_company_frontend_uses_the_scbb_visual_and_research_contract() -> None:
    html = Path("frontend/company.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/company.js").read_text(encoding="utf-8")
    journey = Path("frontend/assets/company-journey.js").read_text(encoding="utf-8")
    css = Path("frontend/assets/company.css").read_text(encoding="utf-8")
    polish = Path("frontend/assets/company-polish.css").read_text(encoding="utf-8")

    assert "COMPANY MONITORING SHEET" in html
    assert "company.css" in html
    assert "company-polish.css" in html
    assert "company.js" in html
    assert "company-journey.js" in html
    assert "scbb-company-v1" in javascript
    for section in (
        "CURRENT VIEW",
        "GUIDANCE",
        "METRICS THAT MATTER",
        "MANAGEMENT PROMISES",
        "WHAT REMAINS UNCLEAR",
        "RNS HISTORY",
    ):
        assert section in javascript
    assert "innerHTML" not in javascript
    assert "innerHTML" not in journey
    assert "company-feed-link" in journey
    assert "var(--cyan)" in css
    assert "var(--page-deep)" in css
    assert "position: absolute" in polish
    assert ".company-history-grid > div > strong" in polish


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
