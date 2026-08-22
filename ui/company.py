from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.company_intelligence import CompanyIntelligenceRepository
from database.product import ProductRepository
from product.formatting import format_day, format_price_change, format_time
from ui.common import (
    ensure_watchlist,
    impact_badge,
    navigate,
    render_brand,
    render_footer,
    safe_http_url,
    toggle_watchlist,
)


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


def _source_link(item: dict[str, Any]) -> str:
    title = _escape(item.get("title") or "Source RNS")
    published_at = str(item.get("published_at") or "")
    try:
        date_text = _escape(format_day(published_at)) if published_at else ""
    except ValueError:
        date_text = ""
    label = " · ".join(part for part in (date_text, title) if part)
    url = safe_http_url(item.get("source_url"))
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
        ("Current guidance", str(len(memory.get("current_guidance") or []))),
        ("Tracked metrics", str(len(memory.get("metric_series") or []))),
        (
            "Open promises",
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


def _latest_view_markup(item: dict[str, Any]) -> str:
    published = str(item.get("published_at") or "")
    date_text = format_day(published) if published else ""
    time_text = format_time(published) if published else ""
    price = item.get("price")
    price_text = (
        format_price_change(price)
        if isinstance(price, dict) and price.get("daily_change_pct") is not None
        else ""
    )
    price_markup = (
        f'<span class="sca-price">{_escape(price_text)}</span>' if price_text else ""
    )
    return (
        '<div class="sca-latest-card">'
        '<div class="sca-meta">'
        f'<span>{_escape(date_text)}</span><span>{_escape(time_text)}</span>'
        f'<span>·</span><span>{_escape(item.get("rns_type"))}</span>'
        '<span class="sca-meta-spacer"></span>'
        f'{impact_badge(str(item.get("impact_colour") or "grey"), str(item.get("impact_level") or "low"))}'
        f"{price_markup}</div>"
        f'<div class="sca-headline">{_escape(item.get("headline"))}</div>'
        f'<div class="sca-takeaway">{_escape(item.get("takeaway"))}</div>'
        "</div>"
    )


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
        st.error("This company is not yet covered by Smallcaps.ai.")
        st.markdown(
            '<div class="sca-body">Company Intelligence appears after the first publishable RNS analysis has been stored.</div>',
            unsafe_allow_html=True,
        )
        if st.button("← Back to AIM Intelligence"):
            navigate("feed")
        render_footer()
        return

    watchlist = ensure_watchlist(default_watchlist)
    top_cols = st.columns([1, .75, 5])
    with top_cols[0]:
        if st.button("← Feed", use_container_width=True):
            navigate("feed")
    with top_cols[1]:
        starred = str(history["ticker"]).upper() in watchlist
        if st.button(
            "★" if starred else "☆",
            use_container_width=True,
            help="Remove from watchlist" if starred else "Add to watchlist",
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
            "Every historical comparison still links back to the earlier RNS."
        )
    else:
        building_copy = (
            "This record is building from RNSs analysed since coverage began. "
            "Smallcaps.ai shows the history it genuinely has and does not invent a backfilled thesis."
        )
    st.markdown(
        f'<div class="sca-building">{_escape(building_copy)}</div>',
        unsafe_allow_html=True,
    )

    announcements = list(history.get("announcements") or [])
    latest = dict(announcements[0]) if announcements else {}
    if latest:
        st.markdown(_section_heading("Latest view"), unsafe_allow_html=True)
        st.markdown(_latest_view_markup(latest), unsafe_allow_html=True)
        latest_cols = st.columns([1, 1, 4.5])
        with latest_cols[0]:
            if st.button(
                "Analyst Note →",
                key="latest-company-note",
                use_container_width=True,
            ):
                navigate("note", source_id=str(latest["source_id"]))
        latest_source = safe_http_url(latest.get("source_url"))
        if latest_source:
            with latest_cols[1]:
                st.link_button(
                    "Original RNS ↗",
                    latest_source,
                    use_container_width=True,
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
    if not announcements:
        st.markdown(
            '<div class="sca-empty">No publishable RNS analysis is available yet.</div>',
            unsafe_allow_html=True,
        )
        render_footer()
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
        item_price = item.get("price")
        price = (
            _escape(format_price_change(item_price))
            if isinstance(item_price, dict)
            and item_price.get("daily_change_pct") is not None
            else ""
        )
        price_markup = f'<span class="sca-price">{price}</span>' if price else ""
        st.markdown(
            '<div class="sca-feed-item">'
            '<div class="sca-meta">'
            f'<span>{_escape(format_day(published))}</span>'
            f'<span>{_escape(format_time(published))}</span><span>·</span>'
            f'<span>{_escape(item["rns_type"])}</span>'
            f'<span class="sca-meta-spacer"></span>{impact}'
            f'{price_markup}</div>'
            f'<div class="sca-headline">{_escape(item["headline"])}</div>'
            f'<div class="sca-takeaway">{_escape(item.get("takeaway"))}</div></div>',
            unsafe_allow_html=True,
        )
        cols = st.columns([1, 1, 4.5])
        with cols[0]:
            if st.button(
                "Analysis →",
                key=f"company-note-{item['source_id']}",
                use_container_width=True,
            ):
                navigate("note", source_id=str(item["source_id"]))
        source_url = safe_http_url(item.get("source_url"))
        if source_url:
            with cols[1]:
                st.link_button(
                    "Original RNS ↗",
                    source_url,
                    use_container_width=True,
                )
    render_footer()
