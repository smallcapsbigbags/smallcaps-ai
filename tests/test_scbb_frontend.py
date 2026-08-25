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


def test_public_root_serves_the_aim_daily_and_rns_monitor_stays_available(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=False)
    with TestClient(app) as client:
        daily = client.get("/")
        rns = client.get("/rns")
        css = client.get("/assets/research.css")
        daily_css = client.get("/assets/daily.css")
        daily_javascript = client.get("/assets/daily.js")
        research_javascript = client.get("/assets/research.js")

    assert daily.status_code == 200
    assert "THE AIM DAILY" in daily.text
    assert "THE AIM MARKET, EDITED FOR YOU" in daily.text
    assert "THE LEAD" in daily.text
    assert "ALSO THIS MORNING" in daily.text
    assert "QUICK TAKES" in daily.text
    assert "THE REST OF AIM" in daily.text
    assert 'href="/rns"' in daily.text

    assert rns.status_code == 200
    assert "AIM RNS feed" in rns.text
    assert "ANALYST MONITORING SHEET" in rns.text
    for heading in (
        "COMPANY / RNS / SIGNAL",
        "WHAT CHANGED",
        "AI VIEW",
        "OUTLOOK",
        "MARKET REACTION",
        "BALANCE SHEET",
        "IMPACT",
    ):
        assert heading in rns.text

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert daily_css.status_code == 200
    assert daily_css.headers["content-type"].startswith("text/css")
    assert daily_javascript.status_code == 200
    assert daily_javascript.headers["content-type"].startswith(
        ("text/javascript", "application/javascript")
    )
    assert research_javascript.status_code == 200
    assert research_javascript.headers["content-type"].startswith(
        ("text/javascript", "application/javascript")
    )
    assert daily.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in daily.headers["content-security-policy"]


def test_legacy_open_deep_link_still_resolves_to_rns_monitor(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=False)
    with TestClient(app) as client:
        response = client.get("/?date=2026-08-21&open=trls-pass1-administration")

    assert response.status_code == 200
    assert "AIM RNS feed" in response.text
    assert "ANALYST MONITORING SHEET" in response.text
    assert "THE AIM DAILY" not in response.text


def test_private_beta_uses_a_server_validated_httponly_cookie(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=True)
    with TestClient(app, follow_redirects=False) as client:
        entrance = client.get("/")
        rejected = client.post("/access", data={"access_code": "wrong"})
        accepted = client.post("/access", data={"access_code": "preview-access"})
        unlocked = client.get("/")
        unlocked_rns = client.get("/rns")
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
    assert "THE AIM DAILY" in unlocked.text
    assert unlocked_rns.status_code == 200
    assert "AIM RNS feed" in unlocked_rns.text
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


def test_aim_daily_source_uses_newsroom_contract_and_journalistic_labels() -> None:
    html = Path("frontend/daily.html").read_text(encoding="utf-8")
    css = Path("frontend/assets/daily.css").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/daily.js").read_text(encoding="utf-8")

    for label in (
        "THE AIM DAILY",
        "THE LEAD",
        "ALSO THIS MORNING",
        "QUICK TAKES",
        "THE REST OF AIM",
    ):
        assert label in html

    assert "aim-daily-newsroom-v1" in javascript
    assert "/api/v1/aim-daily/newsroom" in javascript
    assert "THE VIEW" in javascript
    assert "THE NUMBER" in javascript
    assert "THE CATCH" in javascript
    assert "WHAT'S MISSING" in javascript
    assert "NEXT TEST" in javascript
    assert "AI VIEW" not in html
    assert "AI VIEW" not in javascript
    assert ".innerHTML" not in javascript
    assert "border-radius" in css
    assert "background: var(--page)" in css


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
