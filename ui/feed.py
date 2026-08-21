from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.product import ProductRepository
from product.formatting import attention_count, select_feed_facts
from settings import Settings
from ui.common import (
    ensure_watchlist,
    impact_badge,
    london_now,
    navigate,
    price_markup,
    render_brand,
    toggle_watchlist,
)


def _fact_markup(facts: list[dict[str, Any]]) -> str:
    selected = select_feed_facts(facts, limit=3)
    if not selected:
        return ""
    cells = []
    for fact in selected:
        value = html.escape(str(fact.get("value") or ""))
        label = html.escape(str(fact.get("label") or fact.get("metric") or ""))
        cells.append(
            '<div class="sca-fact">'
            f'<div class="sca-fact-value">{value}</div>'
            f'<div class="sca-fact-label">{label}</div>'
            "</div>"
        )
    return '<div class="sca-facts">' + "".join(cells) + "</div>"


def _render_item(
    item: dict[str, Any],
    *,
    watchlist: set[str],
) -> None:
    ticker = html.escape(str(item["ticker"]))
    company = html.escape(str(item["company"]))
    published = str(item["published_at"])
    time_text = html.escape(published[11:16])
    rns_type = html.escape(str(item["rns_type"]))
    headline = html.escape(str(item["headline"]))
    takeaway = html.escape(str(item["takeaway"]))
    impact = impact_badge(
        str(item["impact_colour"]),
        str(item["impact_level"]),
    )
    price = price_markup(item.get("price"))
    score = int(item.get("impact_score") or 1)
    low = score == 1
    item_class = "sca-feed-item sca-feed-item-low" if low else "sca-feed-item"
    headline_class = (
        "sca-headline sca-headline-critical" if score == 5 else "sca-headline"
    )

    if low:
        st.markdown(
            f"""
            <div class="{item_class}">
              <div class="sca-meta">
                <span>{time_text}</span>
                <span class="sca-ticker">{ticker}</span>
                <span>{company}</span>
                <span>·</span>
                <span>{rns_type}</span>
                <span class="sca-meta-spacer"></span>
                {impact}
                {price}
              </div>
              <div class="sca-summary">{headline}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="{item_class}">
              <div class="sca-meta">
                <span class="sca-ticker">{ticker}</span>
                <span>{company}</span>
                <span>·</span>
                <span>{rns_type}</span>
                <span>·</span>
                <span>{time_text}</span>
                <span class="sca-meta-spacer"></span>
                {impact}
                {price}
              </div>
              <div class="{headline_class}">{headline}</div>
              <div class="sca-takeaway">{takeaway}</div>
              {_fact_markup(list(item.get("key_facts") or []))}
            </div>
            """,
            unsafe_allow_html=True,
        )

    action_cols = st.columns([1.2, 1.1, 1.1, 6])
    with action_cols[0]:
        if st.button(
            "Analyst Note →",
            key=f"note-{item['source_id']}",
            use_container_width=True,
        ):
            navigate("note", source_id=str(item["source_id"]))
    with action_cols[1]:
        if st.button(
            "Company history",
            key=f"company-{item['source_id']}",
            use_container_width=True,
        ):
            navigate("company", ticker=str(item["ticker"]))
    with action_cols[2]:
        starred = str(item["ticker"]).upper() in watchlist
        if st.button(
            "★ Watchlist" if starred else "☆ Watchlist",
            key=f"watch-{item['source_id']}",
            use_container_width=True,
        ):
            toggle_watchlist(str(item["ticker"]))
    source_url = str(item.get("source_url") or "")
    if source_url:
        with action_cols[3]:
            st.link_button(
                "Original RNS ↗",
                source_url,
            )


def render_feed(
    repository: ProductRepository,
    settings: Settings,
) -> None:
    render_brand()
    watchlist = ensure_watchlist(settings.default_watchlist)
    today = london_now().date()

    heading_cols = st.columns([3, 1])
    with heading_cols[0]:
        st.markdown("## AIM Intelligence")
        st.caption("What changed, why it matters, and how the market responded.")
    with heading_cols[1]:
        selected_day = st.date_input(
            "Feed date",
            value=today,
            max_value=today,
            label_visibility="collapsed",
        )

    control_cols = st.columns([2.4, 1, 1.1])
    with control_cols[0]:
        search = st.text_input(
            "Search",
            placeholder="Ticker, company or announcement",
            label_visibility="collapsed",
        )
    with control_cols[1]:
        scope = st.selectbox(
            "Scope",
            ["All AIM", "Watchlist"],
            label_visibility="collapsed",
        )
    with control_cols[2]:
        sort_label = st.selectbox(
            "Sort",
            ["Most Impactful", "Latest"],
            label_visibility="collapsed",
        )

    ticker_filter = watchlist if scope == "Watchlist" else None
    items = repository.list_feed(
        selected_day,
        search=search,
        tickers=ticker_filter,
        sort="latest" if sort_label == "Latest" else "impact",
    )

    if scope == "Watchlist" and not watchlist:
        st.markdown(
            '<div class="sca-empty">Your watchlist is empty. Add companies from the feed.</div>',
            unsafe_allow_html=True,
        )
        return

    if not items:
        st.markdown(
            (
                '<div class="sca-empty">No publishable AIM analysis matches this '
                "view. The daily ingestion worker may not have completed yet.</div>"
            ),
            unsafe_allow_html=True,
        )
        return

    attention = attention_count(items)
    st.markdown(
        (
            f'<div class="sca-summary"><strong>{attention}</strong> announcement'
            f'{"s" if attention != 1 else ""} warrant attention · '
            f"{len(items)} publishable records</div>"
        ),
        unsafe_allow_html=True,
    )

    for item in items:
        _render_item(item, watchlist=watchlist)
