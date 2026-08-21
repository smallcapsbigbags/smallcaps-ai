from __future__ import annotations

import html

import streamlit as st

from database.product import ProductRepository
from product.formatting import format_day, format_price_change, format_time
from ui.common import ensure_watchlist, impact_badge, navigate, render_brand, toggle_watchlist


def render_company(repository: ProductRepository, ticker: str, *, default_watchlist: tuple[str, ...] = ()) -> None:
    render_brand()
    history = repository.company_history(ticker)
    if history is None:
        st.error("That company is not yet covered by Smallcaps.ai.")
        if st.button("← Back to AIM Intelligence"):
            navigate("feed")
        return
    watchlist = ensure_watchlist(default_watchlist)
    top_cols = st.columns([1, 1, 5])
    with top_cols[0]:
        if st.button("← Feed", use_container_width=True):
            navigate("feed")
    with top_cols[1]:
        starred = str(history["ticker"]).upper() in watchlist
        if st.button("★ Watchlist" if starred else "☆ Watchlist", use_container_width=True):
            toggle_watchlist(str(history["ticker"]))
    clean_ticker = html.escape(str(history["ticker"])); company = html.escape(str(history["company"])); count = int(history.get("announcement_count") or 0); coverage_since = str(history.get("coverage_since") or "")
    coverage_copy = f"{count} analysed announcement{'s' if count != 1 else ''}" + (f" · coverage since {format_day(coverage_since)}" if coverage_since else "")
    st.markdown(f'<div class="sca-company-banner"><div class="sca-eyebrow">Company RNS History</div><h1 class="sca-note-title"><span class="sca-ticker">{clean_ticker}</span> · {company}</h1><div class="sca-body">{html.escape(coverage_copy)}</div></div><div class="sca-building">Company Intelligence is building from point-in-time daily coverage. Smallcaps.ai is not backfilling a synthetic 12-month thesis for V1.</div>', unsafe_allow_html=True)
    announcements = list(history.get("announcements") or [])
    if not announcements:
        st.markdown('<div class="sca-empty">No publishable RNS analysis is available yet.</div>', unsafe_allow_html=True)
        return
    if history.get("has_more"):
        st.caption(f"Showing the latest {int(history.get('displayed_count') or len(announcements))} of {count} analysed announcements.")
    for item in announcements:
        published = str(item["published_at"]); headline = html.escape(str(item["headline"])); rns_type = html.escape(str(item["rns_type"])); impact = impact_badge(str(item["impact_colour"]), str(item["impact_level"])); price = html.escape(format_price_change(item.get("price")))
        st.markdown(f'<div class="sca-feed-item"><div class="sca-meta"><span>{html.escape(format_day(published))}</span><span>{html.escape(format_time(published))}</span><span>·</span><span>{rns_type}</span><span class="sca-meta-spacer"></span>{impact}<span class="sca-price">{price}</span></div><div class="sca-headline">{headline}</div><div class="sca-takeaway">{html.escape(str(item.get("takeaway") or ""))}</div></div>', unsafe_allow_html=True)
        cols = st.columns([1.2, 1.1, 6])
        with cols[0]:
            if st.button("Analyst Note →", key=f"company-note-{item['source_id']}", use_container_width=True):
                navigate("note", source_id=str(item["source_id"]))
        source_url = str(item.get("source_url") or "")
        if source_url:
            with cols[1]:
                st.link_button("Original RNS ↗", source_url)
