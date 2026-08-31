from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_watchlist_is_browser_local_and_shared_across_surfaces() -> None:
    store = (ROOT / "frontend" / "assets" / "watchlist.js").read_text(encoding="utf-8")
    assert 'const STORAGE_KEY = "smallcaps-ai-watchlist-v1";' in store
    assert 'const CHANGE_EVENT = "smallcaps:watchlist-change";' in store
    assert "const MAX_TICKERS = 100;" in store
    assert "window.localStorage" in store
    assert "window.SmallcapsWatchlist = Object.freeze" in store
    assert "fetch(" not in store


def test_company_news_exposes_one_combined_rolling_watchlist_feed() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "assets" / "research.js").read_text(encoding="utf-8")

    assert 'id="watchlist-nav-link"' in html
    assert 'href="/rns?watchlist=1"' in html
    assert '/assets/watchlist.css' in html
    assert '/assets/watchlist.js' in html
    assert "const WATCHLIST_RANGE_DAYS = 365;" in js
    assert "const WATCHLIST_MAX_ROWS = 1000;" in js
    assert "loadWatchlistFeed" in js
    assert "fetchAllPages" in js
    assert "ticker: tickers" in js
    assert 'params.get("watchlist") === "1"' in js
    assert 'state.showAll = state.watchlistOnly;' in js
    assert 'controls.feedMode.textContent = state.showAll ? "Watchlist" : "Watchlist · Key News";' in js
    assert '"All updates from companies you follow."' in js
    assert '"saved on this browser"' in js


def test_watchlist_rows_are_starred_without_reusing_signal_colour() -> None:
    js = (ROOT / "frontend" / "assets" / "research.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "assets" / "watchlist.css").read_text(encoding="utf-8")

    assert 'article.dataset.watched = String(isWatched(row.ticker));' in js
    assert 'element("button", "watch-toggle", watched ? "★" : "☆")' in js
    assert 'className = "watch-toggle"' not in js  # built through the safe element helper
    assert '.watch-toggle[aria-pressed="true"]' in css
    assert "var(--blue" in css
    assert "--green" not in css
    assert "--red" not in css
    assert "--amber" not in css
    assert "background: transparent" in css


def test_watchlist_history_shows_dates_and_preserves_forensic_detail() -> None:
    js = (ROOT / "frontend" / "assets" / "research.js").read_text(encoding="utf-8")
    for required in (
        "news-time-watchlist",
        "formatShortDate(row.published_at)",
        "MATERIAL FACTS",
        "CURRENT BASELINE",
        "WHAT CHANGED",
        "MARKET REACTION",
        "NOT DISCLOSED",
        "SOURCE CHECKS",
        "PRE ${formatPrice",
        "DAY ${formatSigned",
    ):
        assert required in js


def test_company_intelligence_can_add_or_remove_the_same_watchlist_ticker() -> None:
    html = (ROOT / "frontend" / "company.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "assets" / "company-watchlist.js").read_text(encoding="utf-8")

    assert 'id="company-watch-toggle"' in html
    assert 'href="/rns?watchlist=1"' in html
    assert '/assets/watchlist.js' in html
    assert '/assets/company-watchlist.js' in html
    assert 'button.textContent = watching ? "★ Watching" : "☆ Watch";' in js
    assert "store.toggle(ticker)" in js


def test_watchlist_empty_state_teaches_the_single_action() -> None:
    js = (ROOT / "frontend" / "assets" / "research.js").read_text(encoding="utf-8")
    assert '"Your watchlist is empty."' in js
    assert '"Star a company in News to build one combined feed."' in js
    assert 'browse.href = "/rns";' in js
