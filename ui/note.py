from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.product import ProductRepository
from product.formatting import (
    format_day,
    format_market_price,
    format_price_context,
    format_time,
)
from ui.common import (
    impact_badge,
    navigate,
    render_brand,
    render_footer,
    safe_http_url,
)


def _html_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    numeric_columns: set[int] | None = None,
) -> str:
    numeric_columns = numeric_columns or set()
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            cls = ' class="num"' if index in numeric_columns else ""
            label = headers[index] if index < len(headers) else ""
            cells.append(
                f'<td{cls} data-label="{html.escape(label, quote=True)}">'
                f"{html.escape(value)}</td>"
            )
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="sca-table-wrap"><table class="sca-table sca-table-responsive"><thead><tr>'
        + head
        + '</tr></thead><tbody>'
        + "".join(body)
        + "</tbody></table></div>"
    )


def _list_markup(items: list[str], empty: str) -> str:
    if not items:
        return f'<div class="sca-body">{html.escape(empty)}</div>'
    return '<ul class="sca-list">' + "".join(
        f"<li>{html.escape(item)}</li>" for item in items
    ) + "</ul>"


def _concept_markup(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    blocks = []
    for item in items:
        term = html.escape(str(item.get("term") or ""))
        meaning = html.escape(str(item.get("plain_english") or ""))
        matters = html.escape(str(item.get("why_it_matters") or ""))
        if not term or not meaning or not matters:
            continue
        blocks.append(
            '<div class="sca-section">'
            f'<div class="sca-section-title">{term}</div>'
            f'<div class="sca-body"><strong>What it means:</strong> {meaning}</div>'
            f'<div class="sca-body"><strong>Why it matters here:</strong> {matters}</div>'
            "</div>"
        )
    return "".join(blocks)


def render_note(
    repository: ProductRepository,
    source_id: str,
    *,
    public_only: bool = True,
) -> None:
    render_brand()
    note = repository.get_note(source_id, public_only=public_only)
    if note is None:
        st.error("This Analyst Note is unavailable.")
        st.markdown(
            '<div class="sca-body">The link may be incomplete, or the analysis may be waiting for owner review.</div>',
            unsafe_allow_html=True,
        )
        if st.button("← Back to AIM Intelligence"):
            navigate("feed")
        render_footer()
        return

    source_urls = [
        url for url in (safe_http_url(value) for value in note.get("source_urls") or []) if url
    ]
    top_cols = st.columns([1, 1.15, 1, 4.5])
    with top_cols[0]:
        if st.button("← Feed", use_container_width=True):
            navigate("feed")
    with top_cols[1]:
        if st.button(
            "Company",
            use_container_width=True,
            help="Open the accumulated Company Intelligence record",
        ):
            navigate("company", ticker=str(note["ticker"]))
    if source_urls:
        with top_cols[2]:
            st.link_button(
                "RNS ↗",
                source_urls[0],
                use_container_width=True,
                help="Open the original regulatory announcement",
            )

    published = str(note["published_at"])
    impact = impact_badge(
        str(note["impact_colour"]),
        str(note["impact_level"]),
    )
    with st.container(key="analyst-note"):
        st.markdown(
            f'<div class="sca-meta"><span class="sca-ticker">{html.escape(str(note["ticker"]))}</span><span>{html.escape(str(note["company"]))}</span><span>·</span><span>{html.escape(str(note["rns_type"]))}</span><span>·</span><span>{html.escape(format_day(published))}</span><span>{html.escape(format_time(published))}</span><span class="sca-meta-spacer"></span>{impact}<span class="sca-price">{html.escape(format_price_context(note.get("price")))}</span></div><h1 class="sca-note-title">{html.escape(str(note["headline"]))}</h1><div class="sca-section-title">What happened & why it matters</div><div class="sca-body">{html.escape(str(note["takeaway"]))}</div>',
            unsafe_allow_html=True,
        )

        facts = []
        calculations = []
        for fact in note.get("key_facts") or []:
            if not str(fact.get("value") or ""):
                continue
            basis = str(fact.get("basis") or "reported")
            if basis == "calculated":
                source_label = "Smallcaps.ai calculation"
                calculation_note = str(fact.get("note") or "").strip()
                if calculation_note:
                    calculations.append(
                        f"{fact.get('label') or fact.get('metric')}: {calculation_note}"
                    )
            elif basis == "reported":
                source_label = "Reported"
            elif basis == "not-disclosed":
                source_label = "Not disclosed"
            else:
                source_label = "Source warning"
            facts.append(
                [
                    str(fact.get("label") or fact.get("metric") or ""),
                    str(fact.get("value") or ""),
                    str(
                        fact.get("previous_value")
                        or fact.get("comparator")
                        or ""
                    ),
                    source_label,
                ]
            )

        st.markdown(
            '<div class="sca-section"></div><div class="sca-section-title">Key numbers</div>',
            unsafe_allow_html=True,
        )
        if facts:
            st.markdown(
                _html_table(
                    ["Metric", "Current", "Previous / comparator", "Source"],
                    facts,
                    numeric_columns={1, 2},
                ),
                unsafe_allow_html=True,
            )
        else:
            st.caption("No decision-useful figures were disclosed.")
        if calculations:
            st.markdown(
                '<div class="sca-section-title">How Smallcaps.ai calculated it</div>'
                + _list_markup(calculations, ""),
                unsafe_allow_html=True,
            )

        change = dict(note.get("what_changed") or {})
        st.markdown(
            f'<div class="sca-section"><div class="sca-section-title">What changed</div><div class="sca-change-grid"><div><div class="sca-change-label">Before</div><div class="sca-change-text">{html.escape(str(change.get("before") or "Coverage building."))}</div></div><div><div class="sca-change-label">Today</div><div class="sca-change-text">{html.escape(str(change.get("today") or ""))}</div></div><div><div class="sca-change-label">Why it matters</div><div class="sca-change-text">{html.escape(str(change.get("read_through") or ""))}</div></div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="sca-section"><div class="sca-section-title">Smallcaps.ai view</div><div class="sca-analyst-view">{html.escape(str(note.get("analyst_view") or ""))}</div><div class="sca-body">This is Smallcaps.ai analysis, not a company-reported fact.</div></div>',
            unsafe_allow_html=True,
        )

        cols = st.columns(2)
        with cols[0]:
            st.markdown(
                '<div class="sca-section"><div class="sca-section-title">What supports the case</div>'
                + _list_markup(
                    list(note.get("supports_case") or []),
                    "No new supporting evidence identified.",
                )
                + "</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                '<div class="sca-section"><div class="sca-section-title">What could go wrong</div>'
                + _list_markup(
                    list(note.get("challenges_case") or []),
                    "No new challenge identified.",
                )
                + "</div>",
                unsafe_allow_html=True,
            )

        guidance = [
            [
                str(event.get("metric") or ""),
                str(event.get("period") or ""),
                str(event.get("value") or "Not disclosed"),
                str(event.get("status") or "").replace("-", " ").title(),
                str(
                    event.get("previous_value")
                    or event.get("comparator")
                    or ""
                ),
            ]
            for event in note.get("guidance_events") or []
        ]
        st.markdown(
            '<div class="sca-section"></div><div class="sca-section-title">Guidance</div>',
            unsafe_allow_html=True,
        )
        if guidance:
            st.markdown(
                _html_table(
                    ["Metric", "Period", "Current position", "Status", "Previous"],
                    guidance,
                    numeric_columns={2, 4},
                ),
                unsafe_allow_html=True,
            )
        else:
            st.caption("No genuine guidance change identified.")

        st.markdown(
            '<div class="sca-section"><div class="sca-section-title">What to watch</div>'
            + _list_markup(
                list(note.get("watch_items") or []),
                "No specific watch item identified.",
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        disclosure = dict(note.get("disclosure_assessment") or {})
        missing = list(disclosure.get("missing_items") or [])
        mismatch = str(
            disclosure.get("management_language_mismatch") or ""
        ).strip()
        if missing:
            st.markdown(
                '<div class="sca-section"><div class="sca-section-title">What is missing</div>'
                + _list_markup(missing, "")
                + "</div>",
                unsafe_allow_html=True,
            )
        if mismatch:
            st.markdown(
                f'<div class="sca-section"><div class="sca-section-title">Management wording check</div><div class="sca-body">{html.escape(mismatch)}</div></div>',
                unsafe_allow_html=True,
            )

        concepts = list(disclosure.get("concept_explanations") or [])
        if concepts:
            st.markdown(
                '<div class="sca-section"></div><div class="sca-section-title">Worth explaining</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_concept_markup(concepts), unsafe_allow_html=True)

        st.markdown(
            '<div class="sca-section"></div><div class="sca-section-title">Market reaction</div>',
            unsafe_allow_html=True,
        )
        price = note.get("price")
        if price:
            currency = str(price.get("currency") or "GBp")
            move = price.get("daily_change_pct")
            rows = [
                [
                    "Event-session move",
                    "—" if move is None else f"{float(move):+.1f}%",
                ],
                [
                    "Previous close",
                    format_market_price(
                        price.get("previous_close"),
                        currency=currency,
                    ),
                ],
                [
                    "Latest / close",
                    format_market_price(
                        price.get("close_price")
                        if price.get("close_price") is not None
                        else price.get("latest_price"),
                        currency=currency,
                    ),
                ],
                ["Source", str(price.get("source") or "")],
            ]
            st.markdown(
                _html_table(
                    ["Measure", "Value"],
                    rows,
                    numeric_columns={1},
                ),
                unsafe_allow_html=True,
            )
        else:
            st.caption("Market reaction will appear once a valid event-session price is available.")

        st.markdown(
            '<div class="sca-section"></div>',
            unsafe_allow_html=True,
        )
        source_cols = st.columns([1.1, 1.2, 4.5])
        if source_urls:
            with source_cols[0]:
                st.link_button(
                    "Original RNS ↗",
                    source_urls[0],
                    use_container_width=True,
                )
        with source_cols[1]:
            if st.button("Company →", use_container_width=True):
                navigate("company", ticker=str(note["ticker"]))
        with source_cols[2]:
            if str(change.get("coverage_status") or "building") == "building":
                st.caption(
                    "Company coverage is building naturally from daily RNS analysis."
                )
    render_footer()
