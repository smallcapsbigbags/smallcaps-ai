from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from web_app import app


def _local_runtime(monkeypatch, *, private_beta: bool) -> None:
    for name in (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("PRIVATE_BETA_MODE", "true" if private_beta else "false")
    monkeypatch.setenv("APP_BETA_PASSWORD", "preview-access")


def test_public_root_serves_the_smallcapsbigbags_monitoring_sheet(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=False)
    with TestClient(app) as client:
        response = client.get("/")
        css = client.get("/assets/research.css")
        javascript = client.get("/assets/research.js")

    assert response.status_code == 200
    assert "AIM RNS feed" in response.text
    assert "ANALYST MONITORING SHEET" in response.text
    for heading in (
        "COMPANY / RNS / SIGNAL",
        "WHAT CHANGED",
        "AI VIEW",
        "OUTLOOK",
        "MARKET REACTION",
        "BALANCE SHEET",
        "IMPACT",
    ):
        assert heading in response.text
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert javascript.status_code == 200
    assert javascript.headers["content-type"].startswith(("text/javascript", "application/javascript"))
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_private_beta_uses_a_server_validated_httponly_cookie(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=True)
    with TestClient(app, follow_redirects=False) as client:
        entrance = client.get("/")
        rejected = client.post("/access", data={"access_code": "wrong"})
        accepted = client.post("/access", data={"access_code": "preview-access"})
        unlocked = client.get("/")
        logged_out = client.post("/logout")

    assert entrance.status_code == 200
    assert "Know what changed" in entrance.text
    assert "See the evidence" in entrance.text
    assert "PRIVATE BETA ACCESS" in entrance.text
    assert rejected.status_code == 401
    assert "not recognised" in rejected.text
    assert accepted.status_code == 303
    assert "httponly" in accepted.headers["set-cookie"].lower()
    assert "samesite=lax" in accepted.headers["set-cookie"].lower()
    assert unlocked.status_code == 200
    assert "AIM RNS feed" in unlocked.text
    assert logged_out.status_code == 303


def test_frontend_source_freezes_the_scbb_visual_and_output_contract() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    css = Path("frontend/assets/research.css").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/research.js").read_text(encoding="utf-8")

    assert "--page: #03080d" in css
    assert "--cyan: #46d7ff" in css
    assert '"Helvetica Neue", Helvetica, Arial, sans-serif' in css
    assert "--sheet-grid:" in css
    assert "border-radius: 0" in css
    assert "@media (max-width: 560px)" in css
    assert "grid-template-columns: var(--sheet-grid)" in css

    for control in (
        "UNIVERSE",
        "COMPANY",
        "RNS TYPE",
        "SIGNAL",
        "IMPACT",
        "SORT",
        "IMPACT 3+",
        "GROUP BY COMPANY",
        "RESET",
    ):
        assert control in html

    assert "/api/v1/monitoring" in javascript
    assert "scbb-monitoring-v1" in javascript
    assert "KEY NUMBERS" in javascript
    assert "DISCLOSURE GAPS / SOURCE WARNINGS" in javascript
    assert "ORIGINAL RNS ↗" in javascript
    assert "textContent" in javascript
    assert ".innerHTML" not in javascript


def test_frontend_does_not_reintroduce_the_old_streamlit_card_language() -> None:
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "frontend/index.html",
            "frontend/assets/research.css",
            "frontend/assets/research.js",
        )
    )
    for forbidden in (
        "CRITICAL · ADVERSE",
        "HIGH · FAVOURABLE",
        "Evidence from the RNS",
        "Read analysis →",
        "sca-feed-card",
        "st.columns",
    ):
        assert forbidden not in combined
