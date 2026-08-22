from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from database.company_memory_query import (
    list_covered_companies,
    load_company_memory_from_database,
)
from database.db import create_database_engine
from settings import Settings

st.set_page_config(page_title="Company Intelligence · Smallcaps.ai", layout="wide")


@st.cache_resource
def _engine():
    settings = Settings.from_env()
    return create_database_engine(settings.database_url)


@st.cache_data(ttl=300)
def _companies() -> list[dict[str, str]]:
    return list_covered_companies(_engine())


def _fmt_date(value: datetime | None) -> str:
    return value.strftime("%d %b %Y") if value else "—"


def _point_line(point) -> str:
    period = f" · {point.period}" if point.period else ""
    return f"**{point.metric}:** {point.value}{period}"


st.markdown("### smallcaps.ai  ·  COMPANY INTELLIGENCE")
st.title("Company Intelligence")
st.caption(
    "What management said, what changed, and what still needs proving. "
    "Built only from RNSs already analysed by Smallcaps.ai."
)

companies = _companies()
if not companies:
    st.info("Company memory will appear after the first analysed RNS is stored.")
    st.stop()

labels = {f"{item['ticker']} · {item['company']}": item for item in companies}
selected_label = st.selectbox("Company", list(labels))
selected = labels[selected_label]
snapshot = load_company_memory_from_database(_engine(), ticker=selected["ticker"])

st.subheader(f"{snapshot.company} · {snapshot.ticker}")
st.caption(
    f"Coverage: {snapshot.coverage_status.title()} · "
    f"From {_fmt_date(snapshot.coverage_started_at)} to "
    f"{_fmt_date(snapshot.latest_announcement_at)}"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Analysed RNSs", snapshot.announcement_count)
col2.metric("Current guidance items", len(snapshot.latest_guidance))
col3.metric("Open management promises", len(snapshot.open_management_claims))
col4.metric("Comparable KPI changes", len(snapshot.calculated_changes))

if snapshot.coverage_status in {"none", "building"}:
    st.info(
        "Memory is still building. This page becomes more useful as each new RNS "
        "adds another verified point of comparison."
    )

st.divider()
st.header("What management is saying now")
if snapshot.latest_guidance:
    for point in snapshot.latest_guidance[:10]:
        st.markdown(_point_line(point))
        detail = " · ".join(
            part
            for part in (
                point.status,
                _fmt_date(point.published_at),
                point.source_title,
            )
            if part
        )
        if detail:
            st.caption(detail)
else:
    st.write("No explicit current guidance has yet been captured.")

st.header("Key numbers over time")
series_with_history = [
    series for series in snapshot.key_metrics if len(series.points) >= 2
]
if series_with_history:
    for series in series_with_history[:8]:
        with st.expander(series.metric, expanded=len(series_with_history) <= 3):
            rows = [
                {
                    "Date": point.published_at.date(),
                    "Period": point.period or "—",
                    "Reported value": point.value,
                    "Numeric": point.value_numeric,
                    "Basis": point.basis.title(),
                    "Source": point.source_title or point.source_id,
                }
                for point in series.points
            ]
            frame = pd.DataFrame(rows)
            st.dataframe(
                frame.drop(columns=["Numeric"]),
                hide_index=True,
                use_container_width=True,
            )
            numeric = frame.dropna(subset=["Numeric"])[["Date", "Numeric"]]
            if len(numeric) >= 2:
                st.line_chart(numeric.set_index("Date"))
else:
    st.write("No KPI has two comparable reported observations yet.")

st.header("Balance sheet and funding")
if snapshot.balance_sheet:
    for point in snapshot.balance_sheet[:8]:
        st.markdown(_point_line(point))
        st.caption(
            f"Reported · {_fmt_date(point.published_at)} · "
            f"{point.source_title or point.source_id}"
        )
else:
    st.write("No comparable cash, debt or funding metric has yet been captured.")

st.header("Management promises to test")
if snapshot.open_management_claims:
    for point in snapshot.open_management_claims[:10]:
        st.markdown(f"**{point.metric}** — {point.value}")
        meta = " · ".join(
            part for part in (point.period, _fmt_date(point.published_at)) if part
        )
        if meta:
            st.caption(meta)
else:
    st.write("No open management promise is currently stored.")

st.header("Smallcaps.ai calculations")
st.caption(
    "These are simple calculations from reported figures, not company-reported facts."
)
if snapshot.calculated_changes:
    for point in snapshot.calculated_changes[:10]:
        st.markdown(f"**{point.metric}:** {point.value}")
        st.caption(point.note)
else:
    st.write("No safe like-for-like calculation is available yet.")

st.header("Recent RNS timeline")
if snapshot.recent_analysis:
    timeline = pd.DataFrame(
        [
            {
                "Date": point.published_at.date(),
                "Impact": point.status or "—",
                "Smallcaps.ai headline": point.value,
                "Announcement": point.source_title,
            }
            for point in snapshot.recent_analysis
        ]
    )
    st.dataframe(timeline, hide_index=True, use_container_width=True)

if snapshot.data_gaps:
    st.header("What is still missing")
    for gap in snapshot.data_gaps:
        st.write(f"— {gap}")

st.caption(
    "Company Intelligence grows automatically from future RNS coverage. "
    "Reported facts, Smallcaps.ai calculations and Smallcaps.ai views remain separate."
)
