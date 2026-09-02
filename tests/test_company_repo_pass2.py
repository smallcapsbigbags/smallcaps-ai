from __future__ import annotations

import re
from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import _asset_version, create_frontend_routes


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_company_repo_pass2_locks_the_decision_hierarchy() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")
    script = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    assert "/assets/company-repo.css?v={{ASSET_VERSION}}" in html
    assert "/assets/company-repo.js?v={{ASSET_VERSION}}" in html
    assert html.index("/assets/company-repo.js") < html.index(
        "/assets/product-shell.js"
    )

    now = script.index('storyCell("NOW"')
    change = script.index('storyCell("CHANGE"')
    watch = script.index('storyCell("WATCH"')
    numbers = script.index('sectionHead("Key numbers"')
    news = script.index('sectionHead("Company news"')
    assert now < change < watch < numbers < news

    assert 'block.dataset.companySection = "current-position"' in script
    assert 'block.dataset.companySection = "key-numbers"' in script
    assert 'block.dataset.companySection = "company-news"' in script
    assert "MAX_KEY_NUMBERS = 6" in script
    assert "INITIAL_NEWS_COUNT = 10" in script


def test_company_repo_pass2_uses_existing_facts_and_explicit_change_only() -> None:
    script = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    for required in (
        "company.current_position",
        "research.takeaway",
        "research.verdict",
        "research.what_changed?.today",
        "research.what_changed?.before",
        "detail.research?.watch_items",
        "company.open_management_claims",
        "company.guidance",
        "company.disclosure_gaps",
        "company.metrics",
        "company.history",
        "meaningfulChange",
        "GENERIC_CHANGE",
    ):
        assert required in script

    # The compact story never introduces a second analyst view or recommendation.
    for forbidden in (
        "analyst_view",
        "supports_case",
        "challenges_case",
        "buy recommendation",
        "sell recommendation",
        "target price",
    ):
        assert forbidden not in script.lower()


def test_company_repo_pass2_keeps_every_number_and_event_source_linked() -> None:
    script = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    assert "metric.points.at(-1)" in script
    assert "latestPoint.source_url" in script
    assert "detail.original_source_url" in script
    assert "item.original_source_url" not in script  # Timeline detail is the canonical source layer.
    assert '"Source ↗"' in script
    assert "function newsHref" in script
    assert 'params.set("date", dateValue)' in script
    assert 'params.set("open", clean(sourceId))' in script
    assert 'return query ? `/rns?${query}` : "/rns";' in script
    assert "details.dataset.sourceId" in script
    assert "activateRequestedAnnouncement" in script


def test_company_repo_pass2_expands_company_news_in_place() -> None:
    script = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    assert 'element("details", `repo-news-item' in script
    assert 'element("summary", "repo-news-summary")' in script
    assert "loadEventDetail" in script
    assert "state.detailCache" in script
    assert 'detailGroup("FACTS")' in script
    assert 'detailGroup("CHANGE")' in script
    assert 'detailGroup("WATCH")' in script
    assert '"NOT DISCLOSED"' in script
    assert "window.location.assign" not in script


def test_company_repo_pass2_adds_no_model_database_or_market_call() -> None:
    script = (ASSETS / "company-repo.js").read_text(encoding="utf-8")

    assert script.count("fetch(") == 2
    assert script.count("/api/v1/company/") == 1
    assert "detailUrl" in script
    for forbidden in (
        "OpenAI",
        "anthropic",
        "database",
        "market-data",
        "XMLHttpRequest",
        "WebSocket",
        "innerHTML",
    ):
        assert forbidden.lower() not in script.lower()


def test_company_repo_pass2_is_dense_responsive_and_keyboard_accessible() -> None:
    script = (ASSETS / "company-repo.js").read_text(encoding="utf-8")
    css = (ASSETS / "company-repo.css").read_text(encoding="utf-8")
    compact = "".join(css.split())

    for selector in (
        ".repo-story-grid",
        ".repo-story-cell",
        ".repo-metric-grid",
        ".repo-news-list",
        ".repo-news-summary",
        ".repo-detail-grid",
        ".repo-more-button",
    ):
        assert selector in css

    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in compact
    assert "@media(max-width:820px)" in compact
    assert "@media(max-width:680px)" in compact
    assert "@media(prefers-reduced-motion:reduce)" in compact
    assert "min-height:44px" in compact
    assert 'event.key === "/"' in script
    assert 'event.key !== "Escape"' in script
    assert "scrollIntoView" in script
    assert "reducedMotion" in script


def test_company_repo_pass2_assets_are_content_fingerprinted(monkeypatch) -> None:
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    for name in (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    client = TestClient(Starlette(routes=create_frontend_routes()))
    response = client.get("/company/SPR")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    expected = _asset_version()
    assert re.search(
        rf'/assets/company-repo\.css\?v={re.escape(expected)}',
        response.text,
    )
    assert re.search(
        rf'/assets/company-repo\.js\?v={re.escape(expected)}',
        response.text,
    )
