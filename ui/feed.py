from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.feed_navigation import latest_publishable_day
from database.product import ProductRepository
from product.formatting import (
    attention_count,
    format_day,
    format_time,
    select_feed_facts,
)
from settings import Settings
from ui.common import (
    ensure_watchlist,
    impact_badge,
    london_now,
    navigate,
    price_markup,
    render_brand,
    render_footer,
    safe_http_url,
    toggle_watchlist,
)


def _fact_markup(facts: list[dict[str, Any]]) -> str:
    selected = select_feed_facts(facts, limit=3)
    if not selected:
        return ""
    cells = []
    for fact in selected:
        basis = str(fact.get("basis") or "reported")
        source_label = "Smallcaps.ai calc" if basis == "calculated" else "Reported"
        cells.append(
            '<div class="sca-fact">'
            '<div class="sca-fact-value">'
            + html.escape(str(fact.get("value") or ""))
            + '</div><div class="sca-fact-label">'
            + html.escape(str(fact.get("label") or fact.get("metric") or ""))
            + '</div><div class="sca-fact-label">'
            + html.escape(source_label)
            + "</div></div>"
        )
    return '<div class="sca-facts">' + "".join(cells) + "</div>"


def _render_actions(item: dict[str, Any], *, watchlist: set[str], low: bool) -> None:
    source_url = safe_http_url(item.get("source_url"))
    if low:
        cols = st.columns(2)
        with cols[0]:
            if st.button(
                "Analysis →",
                key=f"note-{item['source_id']}",
                use_container_width=True,
                help="Open the full Smallcaps.ai Analyst Note",
            ):
                navigate("note", source_id=str(item["source_id"]))
        if source_url:
            with cols[1]:
                st.link_button(
                    "Original RNS ↗",
                    source_url,
                    use_container_width=True,
                )
        return

    cols = st.columns([1, 1, .7, .85])
    with cols[0]:
        if st.button(
            "Analysis →",
            key=f"note-{item['source_id']}",
            use_container_width=True,
            help="Open the full Smallcaps.ai Analyst Note",
        ):
            navigate("note", source_id=str(item["source_id"]))
    with cols[1]:
        if st.button(
            "Company",
            key=f"company-{item['source_id']}",
            use_container_width=True,
            help="Open the accumulated Company Intelligence record",
        ):
            navigate("company", ticker=str(item["ticker"]))
    with cols[2]:
        starred = str(item["ticker"]).upper() in watchlist
        if st.button(
            "★" if starred else "☆",
            key=f"watch-{item['source_id']}",
            use_container_width=True,
            help="Remove from watchlist" if starred else "Add to watchlist",
        ):
            toggle_watchlist(str(item["ticker"]))
    if source_url:
        with cols[3]:
            st.link_button(
                "RNS ↗",
                source_url,
                use_container_width=True,
                help="Open the original regulatory announcement",
            )


def _render_item(item: dict[str, Any], *, watchlist: set[str]) -> None:
    ticker = html.escape(str(item["ticker"]))
    company = html.escape(str(item["company"]))
    time_text = html.escape(format_time(str(item["published_at"])))
    rns_type = html.escape(str(item["rns_type"]))
    headline = html.escape(str(item["headline"]))
    takeaway = html.escape(str(item["takeaway"]))
    impact = impact_badge(str(item["impact_colour"]), str(item["impact_level"]))
    price = price_markup(item.get("price"))
    score = int(item.get("impact_score") or 1)
    low = score == 1
    item_class = "sca-feed-item sca-feed-item-low" if low else "sca-feed-item"

    if low:
        st.markdown(
            f'<div class="{item_class}"><div class="sca-meta"><span>{time_text}</span><span class="sca-ticker">{ticker}</span><span>{company}</span><span>·</span><span>{rns_type}</span><span class="sca-meta-spacer"></span>{impact}{price}</div><div class="sca-summary">{headline}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        headline_class = (
            "sca-headline sca-headline-critical" if score == 5 else "sca-headline"
        )
        analyst_view = html.escape(str(item.get("impact_rationale") or ""))
        analyst_markup = (
            f'<div class="sca-takeaway"><strong>Smallcaps.ai view:</strong> {analyst_view}</div>'
            if analyst_view
            else ""
        )
        st.markdown(
            f'<div class="{item_class}"><div class="sca-meta"><span class="sca-ticker">{ticker}</span><span>{company}</span><span>·</span><span>{rns_type}</span><span>·</span><span>{time_text}</span><span class="sca-meta-spacer"></span>{impact}{price}</div><div class="{headline_class}">{headline}</div><div class="sca-takeaway">{takeaway}</div>{_fact_markup(list(item.get("key_facts") or []))}{analyst_markup}</div>',
            unsafe_allow_html=True,
        )
    _render_actions(item, watchlist=watchlist, low=low)


def _clear_filters() -> None:
    st.session_state["feed_search"] = ""
    st.session_state["feed_scope"] = "All AIM"
    st.session_state["feed_sort"] = "Most Impactful"


def render_feed(repository: ProductRepository, settings: Settings) -> None:
    render_brand()
    watchlist = ensure_watchlist(settings.default_watchlist)
    today = london_now().date()
    latest_day = latest_publishable_day(repository.session_factory) or today
    if latest_day > today:
        latest_day = today
    if "feed_date" not in st.session_state:
        st.session_state["feed_date"] = latest_day

    heading_cols = st.columns([3, 1])
    with heading_cols[0]:
        st.markdown("## AIM Intelligence")
        st.caption("What changed, why it matters, and what to watch next.")
    with heading_cols[1]:
        selected_day = st.date_input(
            "Feed date",
            max_value=today,
            key="feed_date",
            label_visibility="collapsed",
        )

    control_cols = st.columns([2.4, 1, 1.1])
    with control_cols[0]:
        search = st.text_input(
            "Search",
            placeholder="Ticker, company or announcement",
            key="feed_search",
            label_visibility="collapsed",
        )
    with control_cols[1]:
        scope = st.selectbox(
            "Scope",
            ["All AIM", "Watchlist"],
            key="feed_scope",
            label_visibility="collapsed",
        )
    with control_cols[2]:
        sort_label = st.selectbox(
            "Sort",
            ["Most Impactful", "Latest"],
            key="feed_sort",
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
            '<div class="sca-empty"><div class="sca-empty-title">Your watchlist is empty.</div>Add a company from the AIM Intelligence Feed or its Company Intelligence page.</div>',
            unsafe_allow_html=True,
        )
        if st.button("View all AIM announcements", use_container_width=False):
            st.session_state["feed_scope"] = "All AIM"
            st.rerun()
        render_footer()
        return

    if not items:
        filtered = bool(search.strip()) or scope == "Watchlist"
        if filtered:
            st.markdown(
                '<div class="sca-empty"><div class="sca-empty-title">No announcements match these filters.</div>Try another ticker, clear the search or return to All AIM.</div>',
                unsafe_allow_html=True,
            )
            st.button("Clear filters", on_click=_clear_filters)
        else:
            date_label = html.escape(format_day(selected_day))
            st.markdown(
                f'<div class="sca-empty"><div class="sca-empty-title">No publishable AIM analysis for {date_label}.</div>There may have been no market session, or the ingestion worker may still be processing the day.</div>',
                unsafe_allow_html=True,
            )
            if latest_day != selected_day and st.button(
                f"View latest available · {format_day(latest_day)}"
            ):
                st.session_state["feed_date"] = latest_day
                st.rerun()
        render_footer()
        return

    attention = attention_count(items)
    date_label = html.escape(format_day(selected_day))
    st.markdown(
        f'<div class="sca-summary"><strong>{attention}</strong> announcement{"s" if attention != 1 else ""} warrant attention · {len(items)} publishable record{"s" if len(items) != 1 else ""} · {date_label}</div>',
        unsafe_allow_html=True,
    )
    for item in items:
        _render_item(item, watchlist=watchlist)
    render_footer()
