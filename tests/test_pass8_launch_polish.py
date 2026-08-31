from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_company_intelligence_uses_the_light_facts_no_fluff_shell() -> None:
    html = (ROOT / "frontend" / "company.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "assets" / "company-launch.css").read_text(encoding="utf-8")

    assert '<meta name="theme-color" content="#f5f6f8">' in html
    assert '/assets/news.css' in html
    assert '/assets/company-launch.css' in html
    assert '/assets/company-launch.js' in html
    assert "COMPANY INTELLIGENCE" in html
    assert 'href="/rns">News</a>' in html
    assert 'href="/rns?watchlist=1">Watchlist' in html
    assert 'href="/">The AIM Daily</a>' in html
    assert "COMPANY MONITORING SHEET" not in html

    assert "color-scheme: light" in css
    assert "--page: #f5f6f8" in css
    assert "--panel: #ffffff" in css
    assert "--blue: #2563eb" in css
    assert "font-size: clamp(42px, 5.2vw, 64px)" in css
    assert ".company-watch-toggle" in css and "min-height: 44px" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_company_launch_layer_retires_report_language_without_another_data_call() -> None:
    javascript = (ROOT / "frontend" / "assets" / "company-launch.js").read_text(
        encoding="utf-8"
    )

    for required in (
        '"CURRENT VIEW": "LATEST COMPANY NEWS"',
        '"MANAGEMENT PROMISES": "MANAGEMENT COMMITMENTS"',
        '"RNS HISTORY": "COMPANY NEWS HISTORY"',
        'setText(label, "TAKE")',
        'setText(detailsSummary, "VIEW EVIDENCE")',
        'setText(heading, "MATERIAL FACTS")',
        'setText(heading, "NOT DISCLOSED / SOURCE CHECKS")',
        '"VIEW EVIDENCE →"',
        '"OPEN IN NEWS →"',
        '"SOURCE ↗"',
        '"VERY HIGH"',
    ):
        assert required in javascript

    for retired_visible_section in (
        '"AI VIEW"',
        '"WHAT TO WATCH"',
        '"SUPPORTS THE CASE"',
        '"CHALLENGES THE CASE"',
    ):
        assert retired_visible_section in javascript  # explicitly removed by the launch layer

    assert "fetch(" not in javascript
    assert "OpenAI" not in javascript


def test_company_to_news_links_use_the_canonical_company_news_route() -> None:
    javascript = (ROOT / "frontend" / "assets" / "company-journey.js").read_text(
        encoding="utf-8"
    )
    assert 'link.href = `/rns?date=${isoDate}&open=${encodeURIComponent(sourceId)}`;' in javascript
    assert 'link.textContent = "OPEN IN NEWS →";' in javascript
    assert "Company News" in javascript
    assert 'link.href = `/?date=' not in javascript


def test_the_aim_daily_keeps_its_editorial_identity_but_uses_product_vocabulary() -> None:
    html = (ROOT / "frontend" / "daily.html").read_text(encoding="utf-8")

    assert "THE AIM DAILY" in html
    assert "AIM NEWSROOM" in html
    assert 'href="/rns">NEWS</a>' in html
    assert 'href="/rns?watchlist=1">WATCHLIST</a>' in html
    assert "VIEW ALL COMPANY NEWS →" in html
    assert "OPEN COMPANY NEWS →" in html
    assert "RNS MONITOR" not in html
    assert "OPEN RNS MONITOR" not in html


def test_pass8_is_frontend_polish_not_a_new_ai_or_database_feature() -> None:
    company_launch = (ROOT / "frontend" / "assets" / "company-launch.js").read_text(
        encoding="utf-8"
    )
    company_html = (ROOT / "frontend" / "company.html").read_text(encoding="utf-8")

    assert "/api/" not in company_launch
    assert "database" not in company_launch.lower()
    assert "model" not in company_launch.lower()
    assert "OPENAI" not in company_launch.upper()
    assert "company-launch.js" in company_html
