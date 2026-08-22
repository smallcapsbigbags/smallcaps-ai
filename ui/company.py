from __future__ import annotations

import html
from typing import Any
from urllib.parse import urlparse

import streamlit as st

from database.company_intelligence import CompanyIntelligenceRepository
from database.product import ProductRepository
from product.formatting import format_day, format_price_change, format_time
from ui.common import (
    ensure_watchlist,
    impact_badge,
    navigate,
    render_brand,
    toggle_watchlist,
)


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


def _safe_http_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def _source_link(item: dict[str, Any]) -> str:
    title = _escape(item.get("title") or "Source RNS")
    published_at = str(item.get("published_at") or "")
    try:
        date_text = _escape(format_day(published_at)) if published_at else ""
    except ValueError:
        date_text = ""
    label = " · ".join(part for part in (date_text, title) if part)
    url = _safe_http_url(item.get("source_url"))
    if not url:
        return label
    return (
        f'<a class="sca-source-link" href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{label} ↗</a>'
    )


def _table_wrap(markup: str) -> str:
    return f'<div class="sca-table-wrap">{markup}</div>'


def _section_heading(title: str, description: str = "") -> str:
    description_markup = (
        f'<div class="sca-body">{_escape(description)}</div>' if description else ""
    )
    return (
        '<div class="sca-section">'
        f'<div class="sca-section-title">{_escape(title)}</div>'
        f"{description_markup}</div>"
    )


def _summary_cards(memory: dict[str, Any], count: int) -> str:
    items = (
        ("Analysed RNSs", str(count)),
        ("Current guidance items", str(len(memory.get("current_guidance") or []))),
        ("Tracked metrics", str(len(memory.get("metric_series") or []))),
        (
            "Open management promises",
            str(len(memory.get("open_management_claims") or [])),
        ),
    )
    return '<div class="sca-intel-grid">' + "".join(
        '<div class="sca-intel-card">'
        f'<div class="sca-intel-value">{_escape(value)}</div>'
        f'<div class="sca-intel-label">{_escape(label)}</div>'
        "</div>"
        for label, value in items
    ) + "</div>"


def _guidance_markup(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="sca-body">No current guidance has been captured yet.</div>'
    rows = []
    for item in items:
        value = str(item.get("value") or "Not quantified")
        previous = str(item.get("previous_value") or item.get("comparator") or "")
        rows.append(
            "<tr>"
            f'<td><strong>{_escape(item.get("metric"))}</strong></td>'
            f'<td>{_escape(item.get("period"))}</td>'
            f'<td class="num">{_escape(value)}</td>'
            f'<td>{_escape(str(item.get("status") or "").replace("-", " ").title())}</td>'
            f'<td class="num">{_escape(previous)}</td>'
            f'<td>{_source_link(item)}</td>'
            "</tr>"
        )
    table = (
        '<table class="sca-table"><thead><tr>'
        "<th>Metric</th><th>Period</th><th>Current</th><th>Status</th>"
        "<th>Previous / comparator</th><th>Source</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return _table_wrap(table)


def _change_text(series: dict[str, Any]) -> str:
    direction = str(series.get("change_direction") or "unclear")
    percent = series.get("change_percent")
    if direction == "flat":
        return "Unchanged"
    if direction in {"up", "down"} and isinstance(percent, (int, float)):
        return f"{direction.title()} {abs(float(percent)):.1f}%"
    if direction in {"up", "down"}:
        return direction.title()
    return "—"


def _metric_markup(items: list[dict[str, Any]]) -> str:
    if not items:
        return (
            '<div class="sca-body">No repeated decision-useful KPI series are '
            "available yet.</div>"
        )
    rows = []
    for item in items:
        points = list(item.get("points") or [])
        latest = dict(points[-1]) if points else {}
        basis_value = str(item.get("basis") or latest.get("basis") or "reported")
        basis = (
            "Smallcaps.ai calc" if basis_value == "calculated" else "Reported"
        )
        rows.append(
            "<tr>"
            f'<td><strong>{_escape(item.get("label") or item.get("metric"))}</strong>'
            f'<div class="sca-cell-note">{_escape(basis)}</div></td>'
            f'<td>{_escape(item.get("period_family"))}</td>'
            f'<td class="num">{_escape(item.get("latest_value"))}</td>'
            f'<td class="num">{_escape(item.get("previous_value"))}</td>'
            f'<td>{_escape(_change_text(item))}'
            '<div class="sca-cell-note">Smallcaps.ai calculation</div></td>'
            f'<td>{_source_link(latest)}</td>'
            "</tr>"
        )
    table = (
        '<table class="sca-table"><thead><tr>'
        "<th>Metric</th><th>Comparable period</th><th>Latest</th><th>Previous</th>"
        "<th>Change</th><th>Latest source</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return _table_wrap(table)


def _claims_markup(items: list[dict[str, Any]]) -> str:
    if not items:
        return (
            '<div class="sca-body">No open measurable management promises have '
            "been captured yet.</div>"
        )
    blocks = []
    for item in items:
        target_parts = [
            str(item.get("target_value") or "").strip(),
            str(item.get("target_date") or "").strip(),
        ]
        target = " · ".join(part for part in target_parts if part)
        if not target:
            target = "No quantified target"
        blocks.append(
            '<div class="sca-memory-row">'
            '<div class="sca-memory-main">'
            f'<div class="sca-memory-title">{_escape(item.get("claim"))}</div>'
            f'<div class="sca-memory-meta">Target: {_escape(target)} · Status: '
            f'{_escape(str(item.get("status") or "open").replace("-", " ").title())}</div>'
            "</div>"
            f'<div class="sca-memory-source">{_source_link(item)}</div>'
            "</div>"
        )
    return "".join(blocks)


def _resolved_claims_markup(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f'<td>{_escape(item.get("claim"))}</td>'
            f'<td>{_escape(str(item.get("status") or "").replace("-", " ").title())}</td>'
            f'<td>{_escape(item.get("outcome"))}</td>'
            f'<td>{_source_link(item)}</td>'
            "</tr>"
        )
    table = (
        '<table class="sca-table"><thead><tr>'
        "<th>Promise</th><th>Status</th><th>Outcome</th><th>Latest evidence</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return _table_wrap(table)


def _gaps_markup(items: list[dict[str, Any]]) -> str:
    if not items:
        return (
            '<div class="sca-body">No recurring disclosure gap is currently '
            "carried forward.</div>"
        )
    return '<ul class="sca-list">' + "".join(
        f'<li>{_escape(item.get("item"))} '
        f'<span class="sca-cell-note">({_source_link(item)})</span></li>'
        for item in items
    ) + "</ul>"


def render_company(
    repository: ProductRepository,
    intelligence_repository: CompanyIntelligenceRepository,
    ticker: str,
    *,
    default_watchlist: tuple[str, ...] = (),
) -> None:
    render_brand()
    history = repository.company_history(ticker)
    memory = intelligence_repository.get_company_intelligence(ticker)
    if history is None or memory is None:
        st.error("That company is not yet covered by Smallcaps.ai.")
        if st.button("← Back to AIM Intelligence"):
            navigate("feed")
        return

    watchlist = ensure_watchlist(default_watchlist)
    top_cols = st.columns([1, 1.1, 5])
    with top_cols[0]:
        if st.button("← Feed", use_container_width=True):
            navigate("feed")
    with top_cols[1]:
        starred = str(history["ticker"]).upper() in watchlist
        if st.button(
            "★ Watchlist" if starred else "☆ Watchlist",
            use_container_width=True,
        ):
            toggle_watchlist(str(history["ticker"]))

    count = int(history.get("announcement_count") or 0)
    coverage_since = str(history.get("coverage_since") or "")
    coverage_copy = f"{count} analysed announcement{'s' if count != 1 else ''}"
    if coverage_since:
        coverage_copy += f" · coverage since {format_day(coverage_since)}"
    status = str(memory.get("coverage_status") or "building")
    status_label = (
        "Established coverage" if status == "established" else "Coverage building"
    )

    st.markdown(
        '<div class="sca-company-banner">'
        '<div class="sca-eyebrow">Company Intelligence</div>'
        f'<h1 class="sca-note-title"><span class="sca-ticker">{_escape(history["ticker"])}</span> '
        f'· {_escape(history["company"])}</h1>'
        f'<div class="sca-body">{_escape(coverage_copy)} · {_escape(status_label)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if status == "established":
        building_copy = (
            "Coverage spans at least six analysed announcements and 12 months. "
            "This view still uses only point-in-time company disclosures and "
            "Smallcaps.ai calculations based on those disclosures."
        )
    else:
        building_copy = (
            "Company Intelligence is building from the RNSs analysed since coverage "
            "began. Smallcaps.ai does not invent a backfilled 12-month thesis. The "
            "available history is already supplied to the analyst when the next RNS arrives."
        )
    st.markdown(
        f'<div class="sca-building">{_escape(building_copy)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_summary_cards(memory, count), unsafe_allow_html=True)

    st.markdown(_section_heading("Current guidance"), unsafe_allow_html=True)
    st.markdown(
        _guidance_markup(list(memory.get("current_guidance") or [])),
        unsafe_allow_html=True,
    )

    st.markdown(
        _section_heading(
            "Metrics that matter",
            "Repeated comparable figures only. A movement is not automatically good "
            "or bad; the latest Analyst Note explains the consequence.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        _metric_markup(list(memory.get("metric_series") or [])),
        unsafe_allow_html=True,
    )

    st.markdown(_section_heading("Management promises"), unsafe_allow_html=True)
    st.markdown(
        _claims_markup(list(memory.get("open_management_claims") or [])),
        unsafe_allow_html=True,
    )
    resolved = list(memory.get("resolved_management_claims") or [])
    if resolved:
        with st.expander("Delivered, missed or superseded promises"):
            st.markdown(_resolved_claims_markup(resolved), unsafe_allow_html=True)

    st.markdown(_section_heading("What remains unclear"), unsafe_allow_html=True)
    st.markdown(
        _gaps_markup(list(memory.get("disclosure_gaps") or [])),
        unsafe_allow_html=True,
    )

    st.markdown(_section_heading("RNS timeline"), unsafe_allow_html=True)
    announcements = list(history.get("announcements") or [])
    if not announcements:
        st.markdown(
            '<div class="sca-empty">No publishable RNS analysis is available yet.</div>',
            unsafe_allow_html=True,
        )
        return
    if history.get("has_more"):
        st.caption(
            f"Showing the latest {int(history.get('displayed_count') or len(announcements))} "
            f"of {count} analysed announcements."
        )
    for item in announcements:
        published = str(item["published_at"])
        impact = impact_badge(
            str(item["impact_colour"]),
            str(item["impact_level"]),
        )
        price = _escape(format_price_change(item.get("price")))
        st.markdown(
            '<div class="sca-feed-item">'
            '<div class="sca-meta">'
            f'<span>{_escape(format_day(published))}</span>'
            f'<span>{_escape(format_time(published))}</span><span>·</span>'
            f'<span>{_escape(item["rns_type"])}</span>'
            f'<span class="sca-meta-spacer"></span>{impact}'
            f'<span class="sca-price">{price}</span></div>'
            f'<div class="sca-headline">{_escape(item["headline"])}</div>'
            f'<div class="sca-takeaway">{_escape(item.get("takeaway"))}</div></div>',
            unsafe_allow_html=True,
        )
        cols = st.columns([1.2, 1.1, 6])
        with cols[0]:
            if st.button(
                "Analyst Note →",
                key=f"company-note-{item['source_id']}",
                use_container_width=True,
            ):
                navigate("note", source_id=str(item["source_id"]))
        source_url = _safe_http_url(item.get("source_url"))
        if source_url:
            with cols[1]:
                st.link_button("Original RNS ↗", source_url)
