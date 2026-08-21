from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from product.formatting import format_price_change, impact_hex

LONDON = ZoneInfo("Europe/London")

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@500;600;700&display=swap');

:root {
  --sca-bg: #F7F7F5;
  --sca-surface: #FCFCFA;
  --sca-text: #171A1E;
  --sca-muted: #69727A;
  --sca-border: #D8DAD6;
  --sca-blue: #27648A;
  --sca-blue-soft: #EAF1F5;
}

html, body, [class*="css"] {
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp {
  background: var(--sca-bg);
  color: var(--sca-text);
}

header[data-testid="stHeader"] {
  background: transparent;
}

.block-container {
  max-width: 1120px;
  padding-top: 1.75rem;
  padding-bottom: 5rem;
}

#MainMenu, footer {
  visibility: hidden;
}

.sca-brand {
  display: flex;
  align-items: baseline;
  gap: 0.85rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--sca-border);
  margin-bottom: 1.4rem;
}

.sca-brand-name {
  color: var(--sca-text);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.035em;
}

.sca-brand-product {
  color: var(--sca-muted);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sca-eyebrow {
  color: var(--sca-muted);
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.sca-ticker {
  font-family: "Roboto Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.sca-feed-item {
  border-top: 1px solid var(--sca-border);
  padding: 1.15rem 0 0.8rem;
}

.sca-feed-item-low {
  padding: 0.75rem 0 0.45rem;
}

.sca-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  color: var(--sca-muted);
  font-size: 0.78rem;
}

.sca-meta-spacer {
  flex: 1 1 auto;
}

.sca-impact {
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  color: var(--sca-text);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.055em;
  text-transform: uppercase;
  white-space: nowrap;
}

.sca-impact-dot {
  width: 0.58rem;
  height: 0.58rem;
  border-radius: 50%;
  display: inline-block;
}

.sca-price {
  color: var(--sca-text);
  font-family: "Roboto Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}

.sca-headline {
  color: var(--sca-text);
  font-size: 1.12rem;
  font-weight: 650;
  line-height: 1.3;
  letter-spacing: -0.02em;
  margin: 0.75rem 0 0.4rem;
}

.sca-headline-critical {
  font-size: 1.3rem;
}

.sca-takeaway {
  color: #30363B;
  font-size: 0.92rem;
  line-height: 1.55;
  max-width: 850px;
  margin: 0 0 0.7rem;
}

.sca-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.1rem;
  margin-top: 0.7rem;
}

.sca-fact {
  min-width: 130px;
}

.sca-fact-value {
  color: var(--sca-text);
  font-family: "Roboto Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.96rem;
  font-weight: 650;
}

.sca-fact-label {
  color: var(--sca-muted);
  font-size: 0.7rem;
  margin-top: 0.1rem;
}

.sca-summary {
  color: var(--sca-text);
  font-size: 0.88rem;
  margin: 0.45rem 0 1.1rem;
}

.sca-paper {
  background: var(--sca-surface);
  border: 1px solid var(--sca-border);
  padding: 2rem clamp(1.1rem, 4vw, 3.25rem);
  margin-top: 0.7rem;
}

.sca-note-title {
  font-size: clamp(1.75rem, 4vw, 2.55rem);
  line-height: 1.12;
  letter-spacing: -0.045em;
  margin: 1.1rem 0 1rem;
  max-width: 900px;
}

.sca-section {
  border-top: 1px solid var(--sca-border);
  padding-top: 1.3rem;
  margin-top: 1.6rem;
}

.sca-section-title {
  color: var(--sca-muted);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  margin-bottom: 0.7rem;
}

.sca-body {
  color: #2B3136;
  font-size: 0.98rem;
  line-height: 1.68;
  max-width: 900px;
}

.sca-analyst-view {
  border-left: 3px solid var(--sca-blue);
  padding: 0.15rem 0 0.15rem 1rem;
  color: #22282D;
  font-size: 1.02rem;
  line-height: 1.65;
}

.sca-change-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.35rem;
}

.sca-change-label {
  color: var(--sca-muted);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.35rem;
}

.sca-change-text {
  color: #2B3136;
  font-size: 0.9rem;
  line-height: 1.55;
}

.sca-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
}

.sca-table th {
  color: var(--sca-muted);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  text-align: left;
  padding: 0.5rem 0.7rem;
  border-bottom: 1px solid var(--sca-border);
}

.sca-table td {
  padding: 0.65rem 0.7rem;
  border-bottom: 1px solid #E5E6E2;
  vertical-align: top;
}

.sca-table .num {
  font-family: "Roboto Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
}

.sca-list {
  margin: 0;
  padding-left: 1.15rem;
  color: #2B3136;
  font-size: 0.9rem;
  line-height: 1.6;
}

.sca-company-banner {
  border-top: 1px solid var(--sca-border);
  border-bottom: 1px solid var(--sca-border);
  padding: 1.2rem 0;
  margin-bottom: 1.1rem;
}

.sca-building {
  background: var(--sca-blue-soft);
  border-left: 3px solid var(--sca-blue);
  color: #294451;
  padding: 0.85rem 1rem;
  font-size: 0.84rem;
  line-height: 1.5;
  margin: 0.8rem 0 1.3rem;
}

.sca-empty {
  border-top: 1px solid var(--sca-border);
  padding: 2rem 0;
  color: var(--sca-muted);
  font-size: 0.92rem;
}

div[data-testid="stButton"] > button,
div[data-testid="stLinkButton"] > a {
  border-radius: 3px;
  border: 1px solid #C9CCC8;
  background: transparent;
  color: var(--sca-text);
  min-height: 2.1rem;
  font-size: 0.78rem;
  font-weight: 600;
  box-shadow: none;
}

div[data-testid="stButton"] > button:hover,
div[data-testid="stLinkButton"] > a:hover {
  border-color: var(--sca-blue);
  color: var(--sca-blue);
  background: #F4F7F8;
}

div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stTextArea"] textarea {
  border-radius: 3px;
  border-color: #C9CCC8;
  background: var(--sca-surface);
}

@media (max-width: 760px) {
  .block-container {
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .sca-change-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .sca-meta-spacer {
    display: none;
  }

  .sca-paper {
    padding: 1.2rem 1rem;
    border-left: 0;
    border-right: 0;
  }
}
</style>
"""


def inject_styles() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(
        """
        <div class="sca-brand">
          <span class="sca-brand-name">smallcaps.ai</span>
          <span class="sca-brand-product">AIM Intelligence</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def impact_badge(colour: str, level: str) -> str:
    safe_level = html.escape(level.upper())
    return (
        '<span class="sca-impact">'
        f'<span class="sca-impact-dot" style="background:{impact_hex(colour)}"></span>'
        f"IMPACT {safe_level}</span>"
    )


def price_markup(price: dict[str, object] | None) -> str:
    return f'<span class="sca-price">{html.escape(format_price_change(price))}</span>'


def navigate(view: str, **params: str) -> None:
    st.query_params.clear()
    st.query_params["view"] = view
    for key, value in params.items():
        if value:
            st.query_params[key] = value
    st.rerun()


def query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value)


def ensure_watchlist(default_tickers: tuple[str, ...]) -> set[str]:
    if "watchlist_tickers" not in st.session_state:
        st.session_state["watchlist_tickers"] = {
            ticker.upper() for ticker in default_tickers
        }
    return set(st.session_state["watchlist_tickers"])


def toggle_watchlist(ticker: str) -> None:
    current = set(st.session_state.get("watchlist_tickers", set()))
    clean = ticker.upper()
    if clean in current:
        current.remove(clean)
    else:
        current.add(clean)
    st.session_state["watchlist_tickers"] = current
    st.rerun()


def london_now() -> datetime:
    return datetime.now(LONDON)
