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


def test_public_root_serves_the_aim_daily_and_company_news_stays_available(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=False)
    with TestClient(app) as client:
        daily = client.get("/")
        news = client.get("/rns")
        shared_css = client.get("/assets/research.css")
        news_css = client.get("/assets/news.css")
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

    assert news.status_code == 200
    assert "AIM COMPANY NEWS" in news.text
    assert "Facts. No fluff." in news.text
    assert "Every material AIM announcement, reduced to what changed." in news.text
    assert 'id="filters-toggle"' in news.text
    assert 'id="filter-panel"' in news.text
    assert 'id="material-toggle"' in news.text
    assert 'id="feed-mode">Key News' in news.text
    for heading in (
        "Company",
        "News type",
        "Signal",
        "Materiality",
        "Sort",
    ):
        assert heading in news.text
    for retired in (
        "ANALYST MONITORING SHEET",
        "COMPANY / RNS / SIGNAL",
        "AI VIEW",
        "GROUP BY COMPANY",
    ):
        assert retired not in news.text

    assert shared_css.status_code == 200
    assert shared_css.headers["content-type"].startswith("text/css")
    assert news_css.status_code == 200
    assert news_css.headers["content-type"].startswith("text/css")
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


def test_legacy_open_deep_link_still_resolves_to_company_news(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=False)
    with TestClient(app) as client:
        response = client.get("/?date=2026-08-21&open=trls-pass1-administration")

    assert response.status_code == 200
    assert "AIM COMPANY NEWS" in response.text
    assert "Facts. No fluff." in response.text
    assert "THE AIM DAILY" not in response.text


def test_private_beta_uses_a_server_validated_httponly_cookie(monkeypatch) -> None:
    _local_runtime(monkeypatch, private_beta=True)
    with TestClient(app, follow_redirects=False) as client:
        entrance = client.get("/")
        rejected = client.post("/access", data={"access_code": "wrong"})
        accepted = client.post("/access", data={"access_code": "preview-access"})
        unlocked = client.get("/")
        unlocked_news = client.get("/rns")
        logged_out = client.post("/logout")

    assert entrance.status_code == 200
    assert "AIM COMPANY NEWS" in entrance.text
    assert "Facts" in entrance.text and "No fluff" in entrance.text
    assert "PRIVATE BETA ACCESS" in entrance.text
    assert rejected.status_code == 401
    assert "not recognised" in rejected.text
    assert accepted.status_code == 303
    assert "httponly" in accepted.headers["set-cookie"].lower()
    assert "samesite=lax" in accepted.headers["set-cookie"].lower()
    assert unlocked.status_code == 200
    assert "THE AIM DAILY" in unlocked.text
    assert unlocked_news.status_code == 200
    assert "Facts. No fluff." in unlocked_news.text
    assert logged_out.status_code == 303


def test_frontend_source_freezes_the_facts_no_fluff_visual_and_output_contract() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    shared_css = Path("frontend/assets/research.css").read_text(encoding="utf-8")
    news_css = Path("frontend/assets/news.css").read_text(encoding="utf-8")
    javascript = Path("frontend/assets/research.js").read_text(encoding="utf-8")

    # Shared publication styling stays dark for The AIM Daily and Company pages.
    assert "--page: #03080d" in shared_css
    assert "--cyan: #46d7ff" in shared_css

    # Company News owns its light visual layer separately.
    assert "color-scheme: light" in news_css
    assert "--page: #f5f6f8" in news_css
    assert "--surface: #ffffff" in news_css
    assert "--blue: #2563eb" in news_css
    assert '.monitor-row[data-signal="GREEN"]' in news_css
    assert '.monitor-row[data-signal="AMBER"]' in news_css
    assert '.monitor-row[data-signal="RED"]' in news_css
    assert ".impact-dot.filled" in news_css
    assert "border-radius: 9px" in news_css
    assert "@media (max-width: 680px)" in news_css

    for control in (
        "Company",
        "News type",
        "Signal",
        "Materiality",
        "Sort",
        "Reset filters",
    ):
        assert control in html

    assert "/api/v1/monitoring" in javascript
    assert "scbb-monitoring-v1" in javascript
    assert "MATERIAL FACTS" in javascript
    assert "CURRENT BASELINE" in javascript
    assert "WHAT CHANGED" in javascript
    assert "DISCLOSURE GAPS / SOURCE WARNINGS" in javascript
    assert "SOURCE ↗" in javascript
    assert "KEY_NEWS_THRESHOLD = 3" in javascript
    assert "compactWords(row.ai_view || row.what_changed, 45)" in javascript
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
            "frontend/assets/news.css",
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
