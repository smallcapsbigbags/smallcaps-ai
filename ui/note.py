from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.product import ProductRepository
from product.formatting import (
    compact_feed_fact_label,
    compact_feed_fact_value,
    fact_is_numeric,
    feed_comparator_text,
    feed_verdict,
    format_day,
    format_market_price,
    format_time,
    public_rns_type,
    select_feed_facts,
)
from ui.common import (
    impact_badge,
    navigate,
    render_brand,
    render_footer,
    safe_http_url,
)
from ui.note_styles import NOTE_CSS


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


def _list_markup(items: list[str]) -> str:
    clean = [str(item).strip() for item in items if str(item).strip()]
    if not clean:
        return ""
    return '<ul class="sca-note-list">' + "".join(
        f"<li>{html.escape(item)}</li>" for item in clean
    ) + "</ul>"


def _nav_source_urls(note: dict[str, Any]) -> list[str]:
    return [
        url
        for url in (
            safe_http_url(value) for value in note.get("source_urls") or []
        )
        if url
    ]


def _meta_markup(note: dict[str, Any]) -> str:
    published = str(note["published_at"])
    ticker = f'<span class="sca-ticker">{html.escape(str(note["ticker"]))}</span>'
    parts = [
        ticker,
        html.escape(str(note["company"])),
    ]
    rns_type = public_rns_type(note.get("rns_type"))
    if rns_type:
        parts.append(html.escape(rns_type))
    parts.extend(
        [
            html.escape(format_day(published)),
            html.escape(format_time(published)),
        ]
    )
    joined = '<span>·</span>'.join(f"<span>{part}</span>" for part in parts)
    impact = impact_badge(
        str(note.get("impact_colour") or "grey"),
        str(note.get("impact_level") or "low"),
    )
    price = note.get("price") or {}
    price_markup = ""
    move = price.get("daily_change_pct")
    if move is not None:
        phase = "at close" if str(price.get("phase") or "") == "close" else "today"
        price_markup = (
            '<span class="sca-price">'
            + html.escape(f"{float(move):+.1f}% {phase}")
            + "</span>"
        )
    return (
        '<div class="sca-meta sca-note-meta">'
        + joined
        + '<span class="sca-meta-spacer"></span>'
        + impact
        + price_markup
        + "</div>"
    )


def _evidence_markup(facts: list[dict[str, Any]], *, limit: int = 3) -> str:
    selected = select_feed_facts(facts, limit=limit)
    if not selected:
        return ""
    cells: list[str] = []
    for fact in selected:
        label = html.escape(compact_feed_fact_label(fact))
        value = html.escape(compact_feed_fact_value(fact))
        value_class = "sca-note-evidence-value"
        if fact_is_numeric(fact):
            value_class += " sca-note-evidence-value-num"
        comparator = feed_comparator_text(fact)
        comparator_markup = (
            '<div class="sca-note-evidence-comparator">Previous: '
            + html.escape(comparator)
            + "</div>"
            if comparator
            else ""
        )
        calc_markup = (
            '<div class="sca-note-calc">Smallcaps.ai calculation</div>'
            if str(fact.get("basis") or "reported") == "calculated"
            else ""
        )
        cells.append(
            '<div class="sca-note-evidence-item">'
            f'<div class="sca-note-evidence-label">{label}</div>'
            f'<div class="{value_class}">{value}</div>'
            + comparator_markup
            + calc_markup
            + "</div>"
        )
    return (
        '<div class="sca-note-section" data-note-section="evidence">'
        '<div class="sca-note-heading">Evidence from the RNS</div>'
        '<div class="sca-note-evidence-grid">'
        + "".join(cells)
        + "</div></div>"
    )


def _full_fact_rows(facts: list[dict[str, Any]]) -> tuple[list[list[str]], list[str]]:
    rows: list[list[str]] = []
    calculations: list[str] = []
    for fact in facts:
        value = str(fact.get("value") or "").strip()
        if not value:
            continue
        basis = str(fact.get("basis") or "reported")
        if basis == "calculated":
            source_label = "Smallcaps.ai calculation"
            calculation_note = str(fact.get("note") or "").strip()
            if calculation_note:
                calculations.append(
                    f"{compact_feed_fact_label(fact)}: {calculation_note}"
                )
        elif basis == "reported":
            source_label = "Reported"
        elif basis == "not-disclosed":
            source_label = "Not disclosed"
        else:
            source_label = "Source warning"
        rows.append(
            [
                compact_feed_fact_label(fact),
                compact_feed_fact_value(fact),
                feed_comparator_text(fact),
                source_label,
            ]
        )
    return rows, calculations


def _change_markup(change: dict[str, Any]) -> str:
    values = [
        ("Before", str(change.get("before") or "").strip()),
        ("Today", str(change.get("today") or "").strip()),
        ("Why it matters", str(change.get("read_through") or "").strip()),
    ]
    visible = [(label, value) for label, value in values if value]
    if not visible:
        return ""
    return '<div class="sca-note-detail-grid">' + "".join(
        '<div class="sca-note-detail-card">'
        f'<div class="sca-note-detail-label">{html.escape(label)}</div>'
        f'<div class="sca-note-detail-text">{html.escape(value)}</div>'
        "</div>"
        for label, value in visible
    ) + "</div>"


def _concept_markup(items: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for item in items:
        term = str(item.get("term") or "").strip()
        meaning = str(item.get("plain_english") or "").strip()
        matters = str(item.get("why_it_matters") or "").strip()
        if not term or not meaning or not matters:
            continue
        blocks.append(
            '<div class="sca-note-disclosure">'
            f'<div class="sca-note-detail-label">{html.escape(term)}</div>'
            f'<div class="sca-note-detail-text"><strong>What it means:</strong> {html.escape(meaning)}</div>'
            f'<div class="sca-note-detail-text"><strong>Why it matters here:</strong> {html.escape(matters)}</div>'
            "</div>"
        )
    return "".join(blocks)


def _render_navigation(note: dict[str, Any], source_urls: list[str]) -> None:
    with st.container(key="note-nav"):
        cols = st.columns([.75, .8, 1.1, 5.5])
        with cols[0]:
            if st.button("← Feed", use_container_width=True):
                navigate("feed")
        with cols[1]:
            if st.button(
                "Company",
                use_container_width=True,
                help="Open the accumulated Company Intelligence record",
            ):
                navigate("company", ticker=str(note["ticker"]))
        if source_urls:
            with cols[2]:
                st.link_button(
                    "Original RNS ↗",
                    source_urls[0],
                    use_container_width=True,
                    help="Open the original regulatory announcement",
                )


def _render_executive_layer(note: dict[str, Any]) -> None:
    facts = list(note.get("key_facts") or [])
    watch_items = [
        str(item).strip() for item in note.get("watch_items") or [] if str(item).strip()
    ]
    analyst_view = str(note.get("analyst_view") or "").strip()
    st.markdown(
        '<div class="sca-note-shell">'
        + _meta_markup(note)
        + f'<h1 class="sca-note-title">{html.escape(feed_verdict(note))}</h1>'
        + '<div class="sca-note-section" data-note-section="what-happened">'
        + '<div class="sca-note-heading">What happened</div>'
        + f'<div class="sca-note-takeaway">{html.escape(str(note.get("takeaway") or ""))}</div>'
        + "</div>"
        + _evidence_markup(facts, limit=3)
        + (
            '<div class="sca-note-section" data-note-section="our-view">'
            '<div class="sca-note-heading">Our view</div>'
            f'<div class="sca-note-view">{html.escape(analyst_view)}</div>'
            '<div class="sca-note-provenance">Smallcaps.ai analysis — not a company-reported fact.</div>'
            "</div>"
            if analyst_view
            else ""
        )
        + (
            '<div class="sca-note-section" data-note-section="what-to-watch">'
            '<div class="sca-note-heading">What to watch</div>'
            '<div class="sca-note-watch">'
            + _list_markup(watch_items)
            + "</div></div>"
            if watch_items
            else ""
        )
        + '<div class="sca-note-depth"><div class="sca-note-depth-label">Supporting detail</div></div>'
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_depth(note: dict[str, Any]) -> None:
    facts = list(note.get("key_facts") or [])
    fact_rows, calculations = _full_fact_rows(facts)
    change = dict(note.get("what_changed") or {})
    change_markup = _change_markup(change)
    supports = [str(item).strip() for item in note.get("supports_case") or [] if str(item).strip()]
    challenges = [str(item).strip() for item in note.get("challenges_case") or [] if str(item).strip()]
    guidance = [
        [
            str(event.get("metric") or ""),
            str(event.get("period") or ""),
            str(event.get("value") or "Not disclosed"),
            str(event.get("status") or "").replace("-", " ").title(),
            str(event.get("previous_value") or event.get("comparator") or ""),
        ]
        for event in note.get("guidance_events") or []
    ]
    disclosure = dict(note.get("disclosure_assessment") or {})
    missing = [str(item).strip() for item in disclosure.get("missing_items") or [] if str(item).strip()]
    mismatch = str(disclosure.get("management_language_mismatch") or "").strip()
    concepts = list(disclosure.get("concept_explanations") or [])
    concept_markup = _concept_markup(concepts)
    price = note.get("price")

    with st.container(key="note-depth"):
        if change_markup:
            with st.expander("What changed", expanded=False):
                st.markdown(change_markup, unsafe_allow_html=True)

        if fact_rows:
            with st.expander("Full evidence & calculations", expanded=False):
                st.markdown(
                    _html_table(
                        ["Metric", "Current", "Previous", "Source"],
                        fact_rows,
                        numeric_columns={1, 2},
                    ),
                    unsafe_allow_html=True,
                )
                if calculations:
                    st.markdown(
                        '<div class="sca-note-disclosure">'
                        '<div class="sca-note-detail-label">Calculation workings</div>'
                        + _list_markup(calculations)
                        + "</div>",
                        unsafe_allow_html=True,
                    )

        if supports or challenges:
            with st.expander("Investment case detail", expanded=False):
                cols = st.columns(2)
                if supports:
                    with cols[0]:
                        st.markdown(
                            '<div class="sca-note-detail-label">Supports</div>'
                            + _list_markup(supports),
                            unsafe_allow_html=True,
                        )
                if challenges:
                    with cols[1]:
                        st.markdown(
                            '<div class="sca-note-detail-label">Challenges</div>'
                            + _list_markup(challenges),
                            unsafe_allow_html=True,
                        )

        if guidance:
            with st.expander("Guidance", expanded=False):
                st.markdown(
                    _html_table(
                        ["Metric", "Period", "Current position", "Status", "Previous"],
                        guidance,
                        numeric_columns={2, 4},
                    ),
                    unsafe_allow_html=True,
                )

        if missing or mismatch or concept_markup:
            with st.expander("Disclosure & terminology", expanded=False):
                if missing:
                    st.markdown(
                        '<div class="sca-note-disclosure">'
                        '<div class="sca-note-detail-label">What is missing</div>'
                        + _list_markup(missing)
                        + "</div>",
                        unsafe_allow_html=True,
                    )
                if mismatch:
                    st.markdown(
                        '<div class="sca-note-disclosure">'
                        '<div class="sca-note-detail-label">Management wording check</div>'
                        f'<div class="sca-note-detail-text">{html.escape(mismatch)}</div>'
                        "</div>",
                        unsafe_allow_html=True,
                    )
                if concept_markup:
                    st.markdown(concept_markup, unsafe_allow_html=True)

        if price:
            with st.expander("Market reaction", expanded=False):
                currency = str(price.get("currency") or "GBp")
                move = price.get("daily_change_pct")
                rows = [
                    [
                        "Event-session move",
                        "—" if move is None else f"{float(move):+.1f}%",
                    ],
                    [
                        "Previous close",
                        format_market_price(price.get("previous_close"), currency=currency),
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
                    _html_table(["Measure", "Value"], rows, numeric_columns={1}),
                    unsafe_allow_html=True,
                )


def render_note(
    repository: ProductRepository,
    source_id: str,
    *,
    public_only: bool = True,
) -> None:
    st.markdown(NOTE_CSS, unsafe_allow_html=True)
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

    source_urls = _nav_source_urls(note)
    _render_navigation(note, source_urls)
    with st.container(key="analyst-note"):
        _render_executive_layer(note)
        _render_depth(note)
    render_footer()
