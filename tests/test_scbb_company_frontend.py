from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


def test_company_frontend_uses_the_scbb_visual_and_research_contract() -> None:
    html = Path("frontend/company.html").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/company.js").read_text(encoding="utf-8")
    css = Path("frontend/assets/company.css").read_text(encoding="utf-8")
    feed_enhancer = Path("frontend/assets/feed-company.js").read_text(encoding="utf-8")

    assert "COMPANY MONITORING SHEET" in html
    assert "company.css" in html
    assert "company.js" in html
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
    assert "var(--cyan)" in css
    assert "var(--page)" in css
    assert "/company/" in feed_enhancer


def test_private_beta_preserves_the_requested_company_destination(monkeypatch) -> None:
    monkeypatch.setenv("PRIVATE_BETA_MODE", "true")
    monkeypatch.setenv("APP_BETA_PASSWORD", "preview-access")
    app = Starlette(routes=create_frontend_routes())
    client = TestClient(app)

    locked = client.get("/company/SPR")
    assert locked.status_code == 200
    assert 'name="next" value="/company/SPR"' in locked.text
    assert "PRIVATE BETA ACCESS" in locked.text

    unlocked = client.post(
        "/access",
        data={"access_code": "preview-access", "next": "/company/SPR"},
        follow_redirects=False,
    )
    assert unlocked.status_code == 303
    assert unlocked.headers["location"] == "/company/SPR"
    assert "httponly" in unlocked.headers["set-cookie"].lower()


def test_feed_loads_company_navigation_enhancement() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    assert "/assets/company.css" in html
    assert "/assets/feed-company.js" in html
