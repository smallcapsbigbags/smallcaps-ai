import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import create_frontend_routes


@pytest.mark.parametrize("query", [
    "date=2026-08-21&open=trls-pass1-administration", "watchlist=1", "ticker=SPR",
])
def test_root_legacy_news_links_redirect_without_losing_query(monkeypatch, query):
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    with TestClient(Starlette(routes=create_frontend_routes())) as client:
        redirect = client.get(f"/?{query}", follow_redirects=False)
        assert redirect.status_code == 308
        assert redirect.headers["location"] == f"/rns?{query}"
        assert redirect.headers["cache-control"] == "no-store"
        assert "AIM COMPANY NEWS" in client.get(f"/?{query}").text
        assert "See what matters." in client.get("/?utm_source=substack").text
