from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.product import ProductRepository
from product.formatting import format_day, format_market_price, format_price_context, format_time
from ui.common import impact_badge, navigate, render_brand


def _html_table(headers: list[str], rows: list[list[str]], *, numeric_columns: set[int] | None = None) -> str:
    numeric_columns = numeric_columns or set()
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            cls = ' class="num"' if index in numeric_columns else ""
            cells.append(f"<td{cls}>{html.escape(value)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return '<table class="sca-table"><thead><tr>' + head + '</tr></thead><tbody>' + "".join(body) + '</tbody></table>'


def _list_markup(items: list[str], empty: str) -> str:
    if not items:
        return f'<div class="sca-body">{html.escape(empty)}</div>'
    return '<ul class="sca-list">' + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def render_note(repository: ProductRepository, source_id: str, *, public_only: bool = True) -> None:
    render_brand()
    note = repository.get_note(source_id, public_only=public_only)
    if note is None:
        st.error("That Analyst Note is unavailable or not publishable.")
        if st.button("← Back to AIM Intelligence"):
            navigate("feed")
        return
    top_cols = st.columns([1, 5])
    with top_cols[0]:
        if st.button("← Feed", use_container_width=True): navigate("feed")
    with top_cols[1]:
        if st.button(f"{note['ticker']} company history", use_container_width=False): navigate("company", ticker=str(note["ticker"]))
    published = str(note["published_at"]); impact = impact_badge(str(note["impact_colour"]), str(note["impact_level"]))
    with st.container(key="analyst-note"):
        st.markdown(f'<div class="sca-meta"><span class="sca-ticker">{html.escape(str(note["ticker"]))}</span><span>{html.escape(str(note["company"]))}</span><span>·</span><span>{html.escape(str(note["rns_type"]))}</span><span>·</span><span>{html.escape(format_day(published))}</span><span>{html.escape(format_time(published))}</span><span class="sca-meta-spacer"></span>{impact}<span class="sca-price">{html.escape(format_price_context(note.get("price")))}</span></div><h1 class="sca-note-title">{html.escape(str(note["headline"]))}</h1><div class="sca-section-title">The Takeaway</div><div class="sca-body">{html.escape(str(note["takeaway"]))}</div>', unsafe_allow_html=True)
        facts = []
        for fact in note.get("key_facts") or []:
            if not str(fact.get("value") or ""): continue
            status = str(fact.get("information_status") or "")
            facts.append([str(fact.get("label") or fact.get("metric") or ""), str(fact.get("value") or ""), str(fact.get("previous_value") or fact.get("comparator") or ""), status.replace("-", " ").title() if status and status != "new" else ""])
        st.markdown('<div class="sca-section"></div><div class="sca-section-title">Key Numbers</div>', unsafe_allow_html=True)
        if facts: st.markdown(_html_table(["Metric", "Current", "Previous / comparator", "Status"], facts, numeric_columns={1, 2}), unsafe_allow_html=True)
        else: st.caption("No decision-useful figures were disclosed.")
        change = dict(note.get("what_changed") or {})
        st.markdown(f'<div class="sca-section"><div class="sca-section-title">What Changed?</div><div class="sca-change-grid"><div><div class="sca-change-label">Before</div><div class="sca-change-text">{html.escape(str(change.get("before") or "Coverage building."))}</div></div><div><div class="sca-change-label">Today</div><div class="sca-change-text">{html.escape(str(change.get("today") or ""))}</div></div><div><div class="sca-change-label">Read-through</div><div class="sca-change-text">{html.escape(str(change.get("read_through") or ""))}</div></div></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sca-section"><div class="sca-section-title">Analyst View</div><div class="sca-analyst-view">{html.escape(str(note.get("analyst_view") or ""))}</div></div>', unsafe_allow_html=True)
        cols = st.columns(2)
        with cols[0]: st.markdown('<div class="sca-section"><div class="sca-section-title">Supports the Case</div>' + _list_markup(list(note.get("supports_case") or []), "No incremental supporting evidence identified.") + '</div>', unsafe_allow_html=True)
        with cols[1]: st.markdown('<div class="sca-section"><div class="sca-section-title">Challenges the Case</div>' + _list_markup(list(note.get("challenges_case") or []), "No incremental challenge identified.") + '</div>', unsafe_allow_html=True)
        guidance = [[str(event.get("metric") or ""), str(event.get("period") or ""), str(event.get("value") or "Not disclosed"), str(event.get("status") or "").replace("-", " ").title(), str(event.get("previous_value") or event.get("comparator") or "")] for event in note.get("guidance_events") or []]
        st.markdown('<div class="sca-section"></div><div class="sca-section-title">Guidance</div>', unsafe_allow_html=True)
        if guidance: st.markdown(_html_table(["Metric", "Period", "Current position", "Status", "Previous"], guidance, numeric_columns={2, 4}), unsafe_allow_html=True)
        else: st.caption("No genuine guidance event identified.")
        st.markdown('<div class="sca-section"><div class="sca-section-title">What to Watch</div>' + _list_markup(list(note.get("watch_items") or []), "No specific watch item identified.") + '</div>', unsafe_allow_html=True)
        missing = list(dict(note.get("disclosure_assessment") or {}).get("missing_items") or [])
        if missing: st.markdown('<div class="sca-section"><div class="sca-section-title">Disclosure Gaps</div>' + _list_markup(missing, "") + '</div>', unsafe_allow_html=True)
        st.markdown('<div class="sca-section"></div><div class="sca-section-title">Market Reaction</div>', unsafe_allow_html=True)
        price = note.get("price")
        if price:
            currency = str(price.get("currency") or "GBp"); move = price.get("daily_change_pct")
            rows = [["Event-session move", "—" if move is None else f"{float(move):+.1f}%"], ["Previous close", format_market_price(price.get("previous_close"), currency=currency)], ["Latest / close", format_market_price(price.get("close_price") if price.get("close_price") is not None else price.get("latest_price"), currency=currency)], ["Source", str(price.get("source") or "")]]
            st.markdown(_html_table(["Measure", "Value"], rows, numeric_columns={1}), unsafe_allow_html=True)
        else: st.caption("Market reaction will appear once the price worker has run.")
        st.markdown('<div class="sca-section"></div>', unsafe_allow_html=True)
        source_urls = list(note.get("source_urls") or []); source_cols = st.columns([1.2, 1.2, 5])
        if source_urls:
            with source_cols[0]: st.link_button("View original RNS ↗", source_urls[0])
        with source_cols[1]:
            if st.button("Company RNS history →", use_container_width=True): navigate("company", ticker=str(note["ticker"]))
        with source_cols[2]:
            if str(change.get("coverage_status") or "building") == "building": st.caption("Smallcaps.ai company coverage is building naturally from daily RNS analysis.")
