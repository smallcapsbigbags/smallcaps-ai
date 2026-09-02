from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "assets"


def test_company_loads_kpi_integrity_before_the_repository_renderer() -> None:
    html = (FRONTEND / "company.html").read_text(encoding="utf-8")

    css = "/assets/company-kpi-integrity.css?v={{ASSET_VERSION}}"
    enhancer = "/assets/company-kpi-integrity.js?v={{ASSET_VERSION}}"
    renderer = "/assets/company-repo.js?v={{ASSET_VERSION}}"
    assert css in html
    assert enhancer in html
    assert renderer in html
    assert html.index(enhancer) < html.index(renderer)


def test_kpi_enhancer_reuses_the_existing_company_response() -> None:
    script = (ASSETS / "company-kpi-integrity.js").read_text(encoding="utf-8")

    assert "window.fetch = async" in script
    assert "response.clone().json()" in script
    assert 'url.pathname.startsWith("/api/v1/company/")' in script
    assert "nativeFetch(...args)" in script
    assert "metric.trend_points" in script
    assert 'status === "comparable"' in script
    assert "comparable_value_numeric" in script
    assert "source_id" in script
    assert "source_url" in script
    assert "Other periods or units kept separate." in script
    assert "like-for-like period" in script


def test_kpi_sparkline_is_neutral_and_compact() -> None:
    css = (ASSETS / "company-kpi-integrity.css").read_text(encoding="utf-8")

    assert ".repo-sparkline-path" in css
    assert "stroke: var(--blue)" in css
    assert ".repo-metric-trend-caption" in css
    assert "var(--green)" not in css
    assert "var(--red)" not in css
