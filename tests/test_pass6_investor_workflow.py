from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_investor_workflow_assets_are_loaded_by_news_and_company() -> None:
    for name in ("index.html", "company.html"):
        html = (FRONTEND / name).read_text(encoding="utf-8")
        assert "/assets/investor-workflow.css?v={{ASSET_VERSION}}" in html
        assert "/assets/investor-workflow.js?v={{ASSET_VERSION}}" in html
        assert html.index("/assets/product-shell.js") < html.index(
            "/assets/investor-workflow.js"
        )
        assert "The AIM Daily" not in html


def test_investor_workflow_is_deterministic_and_read_only() -> None:
    script = (ASSETS / "investor-workflow.js").read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "innerHTML"):
        assert forbidden not in script

    for required in (
        "HIGH ATTENTION",
        "REVIEW",
        "MATERIAL",
        "What needs attention.",
        "Next checks",
        'data-matter-card="${key}"',
        "Sort highest materiality",
    ):
        assert required in script


def test_attention_rules_only_use_existing_signal_and_materiality() -> None:
    script = (ASSETS / "investor-workflow.js").read_text(encoding="utf-8")
    assert "row.dataset.signal" in script
    assert 'getAttribute("aria-label")' in script
    assert 'signal === "RED" && impact >= 4' in script
    assert 'signal === "AMBER" && impact >= 4' in script
    assert 'signal === "GREEN" && impact >= 4' in script


def test_mobile_controls_and_evidence_navigation_are_explicit() -> None:
    stylesheet = (ASSETS / "investor-workflow.css").read_text(encoding="utf-8")
    script = (ASSETS / "investor-workflow.js").read_text(encoding="utf-8")
    assert "@media (max-width: 760px)" in stylesheet
    assert "min-height: 44px" in stylesheet
    assert "VIEW EVIDENCE →" in script
    assert 'aria-labelledby", "investor-attention-title"' in script
    assert "prefers-reduced-motion: reduce" in stylesheet


def test_retired_daily_workflow_is_not_linked_from_the_product() -> None:
    for name in ("index.html", "company.html", "access.html"):
        html = (FRONTEND / name).read_text(encoding="utf-8")
        assert 'data-product-nav="daily"' not in html
        assert "The AIM Daily" not in html
