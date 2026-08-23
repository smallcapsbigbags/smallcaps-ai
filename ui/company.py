from __future__ import annotations

import html
from typing import Any

import streamlit as st

from database.company_intelligence import CompanyIntelligenceRepository
from database.product import ProductRepository
from product.formatting import (
    feed_verdict,
    format_day,
    format_price_change,
    format_time,
    public_rns_type,
)
from ui.common import (
    ensure_watchlist,
    impact_badge,
    navigate,
    render_brand,
    render_footer,
    safe_http_url,
    toggle_watchlist,
)
from ui.company_styles import COMPANY_CSS


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


def _source_anchor(item: dict[str, Any], label: str = "RNS ↗") -> str:
    url = safe_http_url(item.get("source_url"))
    if not url:
        return ""
    return (
        f'<a class="sca-company-inline-source" href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{_escape(label)}</a>'
    )


def _coverage_line(history: dict[str, Any], memory: dict[str, Any]) -> str:
    count = int(history.get("announcement_count") or 0)
    noun = "analysed RNS" if count == 1 else "analysed RNSs"
    parts: list[str] = []
    coverage_since = str(history.get("coverage_since") or "").strip()
    if coverage_since:
        try:
            parts.append(f"Coverage since {format_day(coverage_since)}")
        except ValueError:
            pass
    parts.append(f"{count} {noun}")
    if str(memory.get("coverage_status") or "building") == "established":
        parts.append("established history")
    else:
        parts.append("history still building")
    return " · ".join(parts)


def _section_intro(key: str, title: str, description: str = "") -> str:
    description_markup = (
        f'<div class="sca-company-cell-value">{_escape(description)}</div>'
        if description
        else ""
    )
    return (
        f'<section class="sca-company-section" data-company-section="{_escape(key)}">'
        '<div class="sca-company-section-label">Company memory</div>'
        f'<div class="sca-company-section-title">{_escape(title)}</div>'
        f"{description_markup}</section>"
    )


def _current_position_markup(note: dict[str, Any]) -> str:
    published = str(note.get("published_at") or "")
    date_text = ""
    time_text = ""
    if published:
        try:
            date_text = format_day(published)
            time_text = format_time(published)
        except ValueError:
            pass
    rns_type = public_rns_type(note.get("rns_type"))
    parts = [part for part in (date_text, time_text, rns_type) if part]
    meta = '<span>·</span>'.join(f"<span>{_escape(part)}</span>" for part in parts)
    impact = impact_badge(
        str(note.get("impact_colour") or "grey"),
        str(note.get("impact_level") or "low"),
    )
    price = note.get("price")
    price_markup = ""
    if isinstance(price, dict) and price.get("daily_change_pct") is not None:
        price_markup = f'<span class="sca-price">{_escape(format_price_change(price))}</span>'
    change = dict(note.get("what_changed") or {})
    view = str(
        note.get("analyst_view")
        or change.get("read_through")
        or note.get("takeaway")
        or ""
    ).strip()
    provenance = (
        f"Latest Smallcaps.ai view · based on the {date_text} RNS"
        if date_text
        else "Latest Smallcaps.ai view"
    )
    return (
        '<div class="sca-company-position" data-company-section="current-position">'
        '<div class="sca-company-section-label">Current position</div>'
        '<div class="sca-company-position-meta">'
        + meta
        + '<span class="sca-meta-spacer"></span>'
        + impact
        + price_markup
        + "</div>"
        f'<div class="sca-company-position-title">{_escape(feed_verdict(note))}</div>'
        + (
            f'<div class="sca-company-position-view">{_escape(view)}</div>'
            f'<div class="sca-company-position-provenance">{_escape(provenance)}</div>'
            if view
            else ""
        )
        + "</div>"
    )


def _guidance_markup(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in items:
        metric = str(item.get("metric") or "").strip()
        if not metric:
            continue
        previous = str(item.get("previous_value") or item.get("comparator") or "").strip()
        previous_markup = (
            '<div><div class="sca-company-cell-label">Previous</div>'
            f'<div class="sca-company-cell-value">{_escape(previous)}</div></div>'
            if previous
            else "<div></div>"
        )
        source = _source_anchor(item)
        source_markup = (
            f'<div class="sca-company-source">{source}</div>' if source else ""
        )
        rows.append(
            '<div class="sca-company-guidance-row">'
            '<div class="sca-company-guidance-grid">'
            '<div><div class="sca-company-cell-label">Guidance</div>'
            f'<div class="sca-company-cell-value sca-company-cell-value-strong">{_escape(metric)}</div>'
            f"{source_markup}</div>"
            '<div><div class="sca-company-cell-label">Period</div>'
            f'<div class="sca-company-cell-value">{_escape(item.get("period"))}</div></div>'
            '<div><div class="sca-company-cell-label">Current</div>'
            f'<div class="sca-company-cell-value sca-company-cell-value-strong">{_escape(item.get("value") or "Not quantified")}</div></div>'
            '<div><div class="sca-company-cell-label">Status</div>'
            f'<div class="sca-company-cell-value">{_escape(str(item.get("status") or "").replace("-", " ").title())}</div></div>'
            + previous_markup
            + "</div></div>"
        )
    return "".join(rows)


def _change_text(series: dict[str, Any]) -> str:
    direction = str(series.get("change_direction") or "unclear")
    percent = series.get("change_percent")
    if direction == "flat":
        return "Unchanged"
    if direction in {"up", "down"} and isinstance(percent, (int, float)):
        return f"{direction.title()} {abs(float(percent)):.1f}%"
    if direction in {"up", "down"}:
        return direction.title()
    return ""


def _metric_cards_markup(items: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in items:
        points = list(item.get("points") or [])
        latest = dict(points[-1]) if points else {}
        previous = str(item.get("previous_value") or "").strip()
        change = _change_text(item)
        if previous and change:
            context = f"{change} from {previous}"
        elif previous:
            context = f"Previous {previous}"
        elif change:
            context = change
        else:
            context = "Latest captured value"
        basis = str(item.get("basis") or latest.get("basis") or "reported")
        basis_label = "Smallcaps.ai calculation" if basis == "calculated" else "Reported"
        source = _source_anchor(latest, "Latest RNS ↗")
        source_markup = f'<div class="sca-company-source">{source}</div>' if source else ""
        cards.append(
            '<div class="sca-company-metric">'
            f'<div class="sca-company-metric-label">{_escape(item.get("label") or item.get("metric"))}</div>'
            f'<div class="sca-company-metric-value">{_escape(item.get("latest_value"))}</div>'
            f'<div class="sca-company-metric-context">{_escape(context)}</div>'
            f'<div class="sca-company-metric-basis">{_escape(basis_label)}</div>'
            f"{source_markup}</div>"
        )
    return '<div class="sca-company-metrics">' + "".join(cards) + "</div>" if cards else ""


def _claims_markup(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in items:
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        target = " · ".join(
            part
            for part in (
                str(item.get("target_value") or "").strip(),
                str(item.get("target_date") or "").strip(),
            )
            if part
        )
        meta = f"Target: {target}" if target else "Open commitment"
        source = _source_anchor(item, "Source RNS ↗")
        if source:
            meta += f" · {source}"
        rows.append(
            '<div class="sca-company-claim-row">'
            f'<div class="sca-company-claim-main">{_escape(claim)}</div>'
            f'<div class="sca-company-claim-meta">{meta}</div>'
            "</div>"
        )
    return "".join(rows)


def _resolved_claims_markup(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in items:
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        status = str(item.get("status") or "").replace("-", " ").title()
        outcome = str(item.get("outcome") or "").strip()
        meta_parts = [part for part in (status, outcome) if part]
        source = _source_anchor(item, "Evidence RNS ↗")
        meta = " · ".join(_escape(part) for part in meta_parts)
        if source:
            meta = f"{meta} · {source}" if meta else source
        rows.append(
            '<div class="sca-company-claim-row">'
            f'<div class="sca-company-claim-main">{_escape(claim)}</div>'
            f'<div class="sca-company-claim-meta">{meta}</div>'
            "</div>"
        )
    return "".join(rows)


def _gaps_markup(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in items:
        gap = str(item.get("item") or "").strip()
        if not gap:
            continue
        source = _source_anchor(item, "Last relevant RNS ↗")
        source_markup = f'<div class="sca-company-gap-meta">{source}</div>' if source else ""
        rows.append(
            '<div class="sca-company-gap-row">'
            f'<div class="sca-company-gap-main">{_escape(gap)}</div>'
            f"{source_markup}</div>"
        )
    return "".join(rows)


def _timeline_markup(item: dict[str, Any]) -> str:
    published = str(item.get("published_at") or "")
    try:
        date_text = format_day(published)
        time_text = format_time(published)
    except ValueError:
        date_text = ""
        time_text = ""
    rns_type = public_rns_type(item.get("rns_type"))
    parts = [part for part in (date_text, time_text, rns_type) if part]
    meta = '<span>·</span>'.join(f"<span>{_escape(part)}</span>" for part in parts)
    impact = impact_badge(
        str(item.get("impact_colour") or "grey"),
        str(item.get("impact_level") or "low"),
    )
    price = item.get("price")
    price_markup = ""
    if isinstance(price, dict) and price.get("daily_change_pct") is not None:
        price_markup = f'<span class="sca-price">{_escape(format_price_change(price))}</span>'
    source = _source_anchor(item, "Original RNS ↗")
    source_markup = f'<div class="sca-company-timeline-source">{source}</div>' if source else ""
    return (
        '<div class="sca-company-timeline-row" data-company-timeline="row">'
        '<div class="sca-company-timeline-top">'
        + meta
        + '<span class="sca-meta-spacer"></span>'
        + impact
        + price_markup
        + "</div>"
        f'<div class="sca-company-timeline-title">{_escape(feed_verdict(item))}</div>'
        f"{source_markup}</div>"
    )


def _render_timeline_items(items: list[dict[str, Any]], *, prefix: str) -> None:
    for index, item in enumerate(items):
        st.markdown(_timeline_markup(item), unsafe_allow_html=True)
        with st.container(key=f"company-timeline-actions-{prefix}-{index}"):
            if st.button(
                "Read analysis →",
                key=f"company-note-{prefix}-{index}-{item['source_id']}",
                help="Open the full Analyst Note",
            ):
                navigate("note", source_id=str(item["source_id"]))


def render_company(
    repository: ProductRepository,
    intelligence_repository: CompanyIntelligenceRepository,
    ticker: str,
    *,
    default_watchlist: tuple[str, ...] = (),
) -> None:
    st.markdown(COMPANY_CSS, unsafe_allow_html=True)
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
    with st.container(key="company-nav"):
        nav_cols = st.columns([.8, 1.05, 5.5])
        with nav_cols[0]:
            if st.button("← Feed", use_container_width=True):
                navigate("feed")
        with nav_cols[1]:
            starred = str(history["ticker"]).upper() in watchlist
            if st.button(
                "★ Watching" if starred else "☆ Watch",
                use_container_width=True,
                help="Remove from watchlist" if starred else "Add to watchlist",
            ):
                toggle_watchlist(str(history["ticker"]))

    st.markdown(
        '<div class="sca-company-shell">'
        '<div class="sca-company-hero">'
        '<div class="sca-company-eyebrow">Company Intelligence</div>'
        f'<h1 class="sca-company-title"><span class="sca-ticker">{_escape(history["ticker"])}</span> · {_escape(history["company"])}</h1>'
        f'<div class="sca-company-coverage">{_escape(_coverage_line(history, memory))}</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    announcements = list(history.get("announcements") or [])
    latest = dict(announcements[0]) if announcements else {}
    latest_note = (
        repository.get_note(str(latest.get("source_id"))) if latest.get("source_id") else None
    )
    latest_view = dict(latest_note or latest)

    if latest_view:
        st.markdown(_current_position_markup(latest_view), unsafe_allow_html=True)
        with st.container(key="company-current-actions"):
            action_cols = st.columns([1.35, 1.05, 3.3])
            with action_cols[0]:
                if st.button(
                    "Read latest analysis →",
                    type="primary",
                    use_container_width=True,
                ):
                    navigate("note", source_id=str(latest["source_id"]))
            source_url = safe_http_url(latest.get("source_url"))
            if source_url:
                with action_cols[1]:
                    st.link_button(
                        "Original RNS ↗",
                        source_url,
                        use_container_width=True,
                    )

    guidance = list(memory.get("current_guidance") or [])
    if guidance:
        st.markdown(_section_intro("guidance", "Guidance"), unsafe_allow_html=True)
        st.markdown(_guidance_markup(guidance), unsafe_allow_html=True)

    metrics = list(memory.get("metric_series") or [])
    if metrics:
        st.markdown(
            _section_intro(
                "metrics",
                "Metrics that matter",
                "The most decision-useful comparable series in the company record.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(_metric_cards_markup(metrics[:3]), unsafe_allow_html=True)
        if len(metrics) > 3:
            with st.container(key="company-more-metrics"):
                with st.expander(f"View all tracked metrics · {len(metrics)}", expanded=False):
                    st.markdown(_metric_cards_markup(metrics[3:]), unsafe_allow_html=True)

    open_claims = list(memory.get("open_management_claims") or [])
    resolved_claims = list(memory.get("resolved_management_claims") or [])
    if open_claims or resolved_claims:
        st.markdown(
            _section_intro("promises", "Management promises"),
            unsafe_allow_html=True,
        )
        if open_claims:
            st.markdown(_claims_markup(open_claims), unsafe_allow_html=True)
        if resolved_claims:
            with st.container(key="company-resolved"):
                with st.expander(
                    f"Delivered, missed or superseded · {len(resolved_claims)}",
                    expanded=False,
                ):
                    st.markdown(
                        _resolved_claims_markup(resolved_claims),
                        unsafe_allow_html=True,
                    )

    gaps = list(memory.get("disclosure_gaps") or [])
    if gaps:
        st.markdown(
            _section_intro("gaps", "What remains unclear"),
            unsafe_allow_html=True,
        )
        st.markdown(_gaps_markup(gaps), unsafe_allow_html=True)

    if announcements:
        st.markdown(
            _section_intro("timeline", "RNS timeline", "How the investment case has developed through published announcements."),
            unsafe_allow_html=True,
        )
        visible = announcements[:12]
        earlier = announcements[12:]
        _render_timeline_items(visible, prefix="recent")
        if earlier:
            with st.container(key="company-earlier"):
                with st.expander(f"Earlier announcements · {len(earlier)}", expanded=False):
                    _render_timeline_items(earlier, prefix="earlier")

    render_footer()
