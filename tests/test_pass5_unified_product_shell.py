from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PAGES = (
    ROOT / "frontend" / "index.html",
    ROOT / "frontend" / "company.html",
)


def test_public_surfaces_share_one_news_watchlist_search_contract() -> None:
    pages = [path.read_text(encoding="utf-8") for path in PUBLIC_PAGES]

    for html in pages:
        assert 'class="' in html and "product-page" in html
        assert '/assets/product-shell.css?v={{ASSET_VERSION}}' in html
        assert '/assets/product-shell.js?v={{ASSET_VERSION}}' in html
        assert 'data-product-nav="news"' in html
        assert 'data-product-nav="watchlist"' in html
        assert 'data-product-nav="daily"' not in html
        assert "data-company-search" in html
        assert "data-company-search-input" in html
        assert 'data-product-status>AIM live</span>' in html
        assert 'data-watchlist-count' in html
        assert 'class="site-footer product-footer' in html
        assert (
            "Independent AIM research. Facts first. Not personal investment advice."
            in html
        )
        assert html.index('data-product-nav="news"') < html.index(
            'data-product-nav="watchlist"'
        ) < html.index("data-company-search")
        assert "The AIM Daily" not in html

    company = pages[1]
    assert 'id="company-context-link"' in company
    assert "← Back to News" in company
    assert "company-repository-page" in company


def test_private_beta_entry_uses_the_same_light_foundation() -> None:
    html = (ROOT / "frontend" / "access.html").read_text(encoding="utf-8")

    assert '<body class="access-body product-access-page">' in html
    assert '<meta name="color-scheme" content="light">' in html
    assert '/assets/news.css?v={{ASSET_VERSION}}' in html
    assert '/assets/product-shell.css?v={{ASSET_VERSION}}' in html
    assert '/assets/research.css' not in html
    assert '/assets/company-polish.css' not in html
    assert '/favicon.svg?v={{ASSET_VERSION}}' in html


def test_shared_shell_owns_safe_news_and_watchlist_context() -> None:
    javascript = (
        ROOT / "frontend" / "assets" / "product-shell.js"
    ).read_text(encoding="utf-8")

    for required in (
        'new Set(["news", "watchlist", "company"])',
        'new Set(["news", "watchlist"])',
        'url.searchParams.set("from", surface)',
        'url.searchParams.set("open", sourceId)',
        'new URLSearchParams({ watchlist: "1" })',
        '"← Back to News"',
        '"← Back to Watchlist"',
        '"Your companies."',
        '"WATCHLIST"',
        "initialiseCompanySearch",
        "MutationObserver",
    ):
        assert required in javascript

    for retired in (
        "daily_state",
        "daily_date",
        "Back to The AIM Daily",
        '"daily"',
    ):
        assert retired not in javascript

    for forbidden in ("fetch(", "XMLHttpRequest", "innerHTML", "OpenAI"):
        assert forbidden not in javascript


def test_shared_shell_enforces_one_mobile_navigation_search_and_footer_layout() -> None:
    css = (ROOT / "frontend" / "assets" / "product-shell.css").read_text(
        encoding="utf-8"
    )
    compact = "".join(css.split())

    assert ".product-page .header-inner" in css
    assert 'grid-template-areas:"brandmeta""navnav""searchsearch"' in compact
    assert ".product-page .primary-nav" in css
    assert ".product-page .company-search" in css
    assert ".product-page .product-footer-links" in css
    assert ".product-page .company-context-link" in css
    assert ".company-news-page[data-product-surface=\"watchlist\"]" in css
    assert "min-height:44px" in compact
    assert "@media(max-width:760px)" in compact
    assert "@media(prefers-reduced-motion:reduce)" in compact


def test_watchlist_css_no_longer_owns_company_controls() -> None:
    css = (ROOT / "frontend" / "assets" / "watchlist.css").read_text(
        encoding="utf-8"
    )

    assert ".watch-toggle" in css
    assert ".watchlist-nav-count" in css
    assert ".company-watch-toggle" not in css


def test_daily_files_are_retained_only_for_final_migration_cleanup() -> None:
    assert (ROOT / "frontend" / "daily.html").exists()
    for path in PUBLIC_PAGES:
        html = path.read_text(encoding="utf-8")
        assert "The AIM Daily" not in html
        assert 'data-product-nav="daily"' not in html
