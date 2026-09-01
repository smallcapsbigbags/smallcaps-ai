from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def _client(monkeypatch) -> TestClient:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    for name in (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    return TestClient(Starlette(routes=create_frontend_routes()))


def test_company_news_is_the_product_front_door(monkeypatch) -> None:
    client = _client(monkeypatch)

    home = client.get("/")
    news = client.get("/rns")

    assert home.status_code == 200
    assert news.status_code == 200
    for response in (home, news):
        assert "AIM COMPANY NEWS" in response.text
        assert "Facts. No fluff." in response.text
        assert "What changed across AIM." in response.text
        assert "THE AIM DAILY" not in response.text
        assert 'data-product-nav="daily"' not in response.text


def test_public_shell_is_only_news_watchlist_and_company_search() -> None:
    for name in ("index.html", "company.html"):
        html = (FRONTEND / name).read_text(encoding="utf-8")
        assert html.count('data-product-nav="news"') == 1
        assert html.count('data-product-nav="watchlist"') == 1
        assert 'data-product-nav="daily"' not in html
        assert "The AIM Daily" not in html
        assert "data-company-search" in html
        assert "data-company-search-input" in html
        assert "data-company-search-options" in html
        assert html.index('data-product-nav="news"') < html.index(
            'data-product-nav="watchlist"'
        ) < html.index("data-company-search")


def test_company_page_uses_repository_language() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")

    assert "Smallcaps.ai · Company" in html
    assert '<p class="eyebrow">Company</p>' in html
    assert "Loading company…" in html
    assert "Building company history…" in html
    assert "company-repository-page" in html
    assert "Company Intelligence" not in html
    assert "The AIM Daily" not in html


def test_company_search_is_local_deterministic_and_context_safe() -> None:
    javascript = (ASSETS / "product-shell.js").read_text(encoding="utf-8")

    assert 'new Set(["news", "watchlist", "company"])' in javascript
    assert 'new Set(["news", "watchlist"])' in javascript
    assert "initialiseCompanySearch" in javascript
    assert "data-company-search-input" in javascript
    assert "normaliseTicker" in javascript
    assert 'new URLSearchParams({ from: context })' in javascript
    assert 'window.location.assign(`/company/' in javascript
    for retired in (
        '"daily"',
        "DAILY_STATES",
        "daily_state",
        "daily_date",
        "Back to The AIM Daily",
    ):
        assert retired not in javascript
    for forbidden in ("fetch(", "XMLHttpRequest", "innerHTML", "OpenAI"):
        assert forbidden not in javascript


def test_daily_assets_are_dormant_not_customer_linked() -> None:
    # Pass 1 removes the Daily from the product without deleting its historical
    # backend or files. Physical deletion is reserved for the final migration pass.
    assert (FRONTEND / "daily.html").exists()
    for name in ("index.html", "company.html", "access.html"):
        html = (FRONTEND / name).read_text(encoding="utf-8")
        assert 'href="/daily"' not in html
        assert 'data-product-nav="daily"' not in html
