from __future__ import annotations

import re

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import _asset_version, create_frontend_routes


ASSET_PATTERN = re.compile(r"(?:href|src)=\"(/assets/[^\"]+\?v=([0-9a-f]{12}))\"")


def _client(monkeypatch) -> TestClient:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_ID", raising=False)
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
    return TestClient(Starlette(routes=create_frontend_routes()))


def test_customer_html_uses_one_content_fingerprinted_asset_set(monkeypatch) -> None:
    client = _client(monkeypatch)
    expected = _asset_version()

    for path in ("/rns", "/", "/company/SPR"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "{{ASSET_VERSION}}" not in response.text
        assets = ASSET_PATTERN.findall(response.text)
        assert assets, path
        assert {version for _url, version in assets} == {expected}


def test_company_news_bootstrap_script_is_versioned(monkeypatch) -> None:
    response = _client(monkeypatch).get("/rns")

    assert response.status_code == 200
    assert f'/assets/research.js?v={_asset_version()}' in response.text
    assert f'/assets/watchlist.js?v={_asset_version()}' in response.text
    assert 'src="/assets/research.js"' not in response.text


def test_primary_navigation_order_is_consistent(monkeypatch) -> None:
    client = _client(monkeypatch)

    for path in ("/rns", "/", "/company/SPR"):
        html = client.get(path).text
        news = html.index('href="/rns"')
        watchlist = html.index('href="/rns?watchlist=1"')
        daily = html.index('href="/"', html.index("Primary navigation"))
        assert news < watchlist < daily, path
