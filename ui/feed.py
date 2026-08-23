from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.feed_navigation import latest_publishable_day
from database.product import ProductRepository
from product.formatting import (
    attention_count,
    fact_is_numeric,
    format_day,
    format_time,
    public_rns_type,
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
from ui.feed_styles import FEED_CSS


def _join_meta(parts: list[str]) -> str:
    return '<span>·</span>'.join(f"<span>{part}</span>" for part in parts if part)


def _meta_markup(item: dict[str, Any]) -> str:
    ticker = f'<span class="sca-ticker">{html.escape(str(item["ticker"]))}</span>'
    company = html.escape(str(item["company"]))
    rns_type = public_rns_type(item.get("rns_type"))
    time_text = html.escape(format_time(str(item["published_at"])))

    parts = [ticker, company]
    if rns_type:
        parts.append(html.escape(rns_type))
    parts.append(time_text)

    impact = impact_badge(
        str(item.get("impact_colour") or "grey"),
        str(item.get("impact_level") or "low"),
    )
    price = price_markup(item.get("price"))
    return (
        '<div class="sca-meta">'
        + _join_meta(parts)
        + '<span class="sca-meta-spacer"></span>'
        + impact
        + price
        + "</div>"
    )


def _fact_markup(facts: list[dict[str, Any]]) -> str:
    selected = select_feed_facts(facts, limit=3)
    if not selected:
        return ""

    narrative = any(not fact_is_numeric(fact) for fact in selected)
    grid_class = (
        "sca-evidence-grid sca-evidence-grid-narrative"
        if narrative
        else "sca-evidence-grid"
    )
    cells: list[str] = []
    for fact in selected:
        label = html.escape(
            str(fact.get("label") or fact.get("metric") or "Reported fact")
        )
        value = html.escape(str(fact.get("value") or ""))
        value_class = "sca-evidence-value"
        if fact_is_numeric(fact):
            value_class += " sca-evidence-value-numeric"

        previous = str(
            fact.get("previous_value") or fact.get("comparator") or ""
        ).strip()
        comparator_markup = ""
        if previous and previous != str(fact.get("value") or "").strip():
            comparator_markup = (
                '<div class="sca-evidence-comparator">Previous / comparator: '
                + html.escape(previous)
                + "</div>"
            )

        basis_markup = ""
        if str(fact.get("basis") or "reported") == "calculated":
            basis_markup = (
                '<div class="sca-evidence-basis">Smallcaps.ai calculation</div>'
            )

        cells.append(
            '<div class="sca-evidence-item">'
            f'<div class="sca-evidence-label">{label}</div>'
            f'<div class="{value_class}">{value}</div>'
            + comparator_markup
            + basis_markup
            + "</div>"
        )

    return (
        '<div class="sca-evidence">'
        '<div class="sca-evidence-heading">Evidence</div>'
        f'<div class="{grid_class}">'
        + "".join(cells)
        + "</div></div>"
    )


def _material_markup(item: dict[str, Any]) -> str:
    score = int(item.get("impact_score") or 1)
    record_class = "sca-feed-record"
    if score == 5:
        record_class += " sca-feed-record-critical"

    headline = html.escape(str(item.get("headline") or ""))
    takeaway = html.escape(str(item.get("takeaway") or ""))
    analyst_view = html.escape(str(item.get("impact_rationale") or ""))
    view_markup = ""
    if analyst_view:
        view_markup = (
            '<div class="sca-feed-view">'
            '<div class="sca-feed-view-label">Smallcaps.ai view</div>'
            f'<div class="sca-feed-view-text">{analyst_view}</div>'
            "</div>"
        )

    return (
        f'<article class="{record_class}" data-feed-kind="material">'
        + _meta_markup(item)
        + f'<div class="sca-feed-verdict">{headline}</div>'
        + f'<div class="sca-feed-takeaway">{takeaway}</div>'
        + _fact_markup(list(item.get("key_facts") or []))
        + view_markup
        + "</article>"
    )


def _routine_markup(item: dict[str, Any]) -> str:
    headline = html.escape(str(item.get("headline") or ""))
    return (
        '<article class="sca-routine-record" data-feed-kind="routine">'
        + _meta_markup(item)
        + f'<div class="sca-routine-headline">{headline}</div>'
        + "</article>"
    )


def _render_actions(
    item: dict[str, Any],
    *,
    watchlist: set[str],
    routine: bool,
) -> None:
    source_id = str(item["source_id"])
    source_url = safe_http_url(item.get("source_url"))

    with st.container(key=f"feed-actions-{source_id}"):
        if routine:
            cols = st.columns([1.3, 1])
            with cols[0]:
                if st.button(
                    "Read analysis →",
                    key=f"feed-primary-{source_id}",
                    type="primary",
                    use_container_width=True,
                    help="Open the full Smallcaps.ai Analyst Note",
                ):
                    navigate("note", source_id=source_id)
            if source_url:
                with cols[1]:
                    st.link_button(
                        "Original RNS ↗",
                        source_url,
                        use_container_width=True,
                    )
            return

        cols = st.columns([1.4, .8, 1, .9])
        with cols[0]:
            if st.button(
                "Read analysis →",
                key=f"feed-primary-{source_id}",
                type="primary",
                use_container_width=True,
                help="Open the full Smallcaps.ai Analyst Note",
            ):
                navigate("note", source_id=source_id)
        with cols[1]:
            if st.button(
                "Company",
                key=f"feed-company-{source_id}",
                use_container_width=True,
                help="Open the accumulated Company Intelligence record",
            ):
                navigate("company", ticker=str(item["ticker"]))
        if source_url:
            with cols[2]:
                st.link_button(
                    "Original RNS ↗",
                    source_url,
                    use_container_width=True,
                    help="Open the original regulatory announcement",
                )
        with cols[3]:
            starred = str(item["ticker"]).upper() in watchlist
            if st.button(
                "★ Watching" if starred else "☆ Watch",
                key=f"feed-watch-{source_id}",
                use_container_width=True,
                help="Remove from watchlist" if starred else "Add to watchlist",
            ):
                toggle_watchlist(str(item["ticker"]))


def _render_item(
    item: dict[str, Any],
    *,
    watchlist: set[str],
    routine: bool,
) -> None:
    st.markdown(
        _routine_markup(item) if routine else _material_markup(item),
        unsafe_allow_html=True,
    )
    _render_actions(item, watchlist=watchlist, routine=routine)


def _clear_filters() -> None:
    st.session_state["feed_search"] = ""
    st.session_state["feed_scope"] = "All AIM"
    st.session_state["feed_sort"] = "Most Impactful"


def render_feed(repository: ProductRepository, settings: Settings) -> None:
    st.markdown(FEED_CSS, unsafe_allow_html=True)
    render_brand()
    watchlist = ensure_watchlist(settings.default_watchlist)
    today = london_now().date()
    latest_day = latest_publishable_day(repository.session_factory) or today
    if latest_day > today:
        latest_day = today
    if "feed_date" not in st.session_state:
        st.session_state["feed_date"] = latest_day
    if "feed_scope" not in st.session_state:
        st.session_state["feed_scope"] = "All AIM"
    if "feed_sort" not in st.session_state:
        st.session_state["feed_sort"] = "Most Impactful"

    st.markdown(
        '<div class="sca-feed-hero">'
        '<h1 class="sca-feed-title">AIM Intelligence</h1>'
        '<p class="sca-feed-deck">Every AIM announcement. The change, the evidence and the Smallcaps.ai view.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container(key="feed-controls"):
        search = st.text_input(
            "Search",
            placeholder="Ticker, company or announcement",
            key="feed_search",
            label_visibility="collapsed",
        )

    current_day = format_day(str(st.session_state["feed_date"]))
    with st.container(key="feed-filter-panel"):
        with st.expander(f"Date & filters · {current_day}", expanded=False):
            control_cols = st.columns(3)
            with control_cols[0]:
                selected_day = st.date_input(
                    "Feed date",
                    max_value=today,
                    key="feed_date",
                )
            with control_cols[1]:
                scope = st.selectbox(
                    "Scope",
                    ["All AIM", "Watchlist"],
                    key="feed_scope",
                )
            with control_cols[2]:
                sort_label = st.selectbox(
                    "Sort",
                    ["Most Impactful", "Latest"],
                    key="feed_sort",
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
    st.markdown(
        '<div class="sca-feed-summary">'
        f'<strong>{attention} need attention</strong>'
        '<span class="sca-feed-summary-separator">·</span>'
        f'<span>{len(items)} analysed announcement{"s" if len(items) != 1 else ""}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    if sort_label == "Latest":
        for item in items:
            routine = int(item.get("impact_score") or 1) == 1
            _render_item(item, watchlist=watchlist, routine=routine)
        render_footer()
        return

    material_items = [
        item for item in items if int(item.get("impact_score") or 1) > 1
    ]
    routine_items = [
        item for item in items if int(item.get("impact_score") or 1) == 1
    ]

    for item in material_items:
        _render_item(item, watchlist=watchlist, routine=False)

    if routine_items:
        with st.container(key="feed-routine"):
            with st.expander(
                f"Routine announcements · {len(routine_items)}",
                expanded=bool(search.strip()) or not material_items,
            ):
                for item in routine_items:
                    _render_item(item, watchlist=watchlist, routine=True)

    render_footer()
