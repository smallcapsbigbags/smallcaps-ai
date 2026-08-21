from __future__ import annotations

import hmac
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from analyst.analyzer import OpenAIAnalystEngine
from database.product import ProductRepository
from database.repository import IntelligenceRepository
from ingestion.manual import build_manual_announcement
from pipeline import AnalysisBlockedError, FoundationPipeline
from settings import Settings
from ui.common import navigate, render_brand

LONDON = ZoneInfo("Europe/London")


def require_admin_access(settings: Settings) -> None:
    if not settings.app_admin_password:
        st.error(
            "The private Analyst QA console is disabled because "
            "APP_ADMIN_PASSWORD is not configured."
        )
        st.stop()
    if st.session_state.get("admin_access_granted"):
        return

    render_brand()
    st.caption("Private Analyst QA")
    with st.form("admin-access", clear_on_submit=True):
        supplied = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("UNLOCK")
    if submitted and hmac.compare_digest(
        supplied,
        settings.app_admin_password,
    ):
        st.session_state["admin_access_granted"] = True
        st.rerun()
    if submitted:
        st.error("That access code is not valid.")
    st.stop()


def render_admin(
    settings: Settings,
    intelligence_repository: IntelligenceRepository,
    product_repository: ProductRepository,
) -> None:
    require_admin_access(settings)
    render_brand()

    nav_cols = st.columns([1, 6])
    with nav_cols[0]:
        if st.button("← Public Feed", use_container_width=True):
            navigate("feed")

    st.markdown("## Analyst QA")
    st.caption(
        "Manual ingestion is a QA/recovery path. The daily product uses "
        "Investegate discovery → OpenAI evidence retrieval → Analyst Engine 2.0."
    )

    queue = product_repository.list_review_queue()
    with st.expander(
        f"Owner review queue · {len(queue)}",
        expanded=bool(queue),
    ):
        if not queue:
            st.caption("No current review-required records.")
        for item in queue:
            cols = st.columns([1, 5, 1])
            with cols[0]:
                st.code(str(item["ticker"]), language=None)
            with cols[1]:
                st.write(item["headline"])
                for flag in item.get("quality_flags") or []:
                    st.caption(str(flag.get("message") or flag))
            with cols[2]:
                if st.button(
                    "Inspect",
                    key=f"review-{item['source_id']}",
                    use_container_width=True,
                ):
                    note = product_repository.get_note(
                        str(item["source_id"]),
                        public_only=False,
                    )
                    st.session_state["admin_preview"] = note

    preview = st.session_state.get("admin_preview")
    if preview:
        with st.expander("Selected review record", expanded=True):
            st.json(preview)

    with st.form("manual-rns"):
        c1, c2 = st.columns(2)
        with c1:
            ticker = st.text_input("Ticker", placeholder="IHC")
            company = st.text_input(
                "Company",
                placeholder="Inspiration Healthcare Group",
            )
            title = st.text_input(
                "Announcement title",
                placeholder="Grant of awards under LTIP",
            )
            rns_type = st.selectbox(
                "Announcement type",
                [
                    "Results & trading",
                    "Contracts",
                    "Fundraising",
                    "Director dealing",
                    "Holdings",
                    "Remuneration",
                    "Board & advisers",
                    "Corporate",
                    "Other",
                ],
                index=8,
            )
        with c2:
            publication_date = st.date_input("Publication date")
            publication_time = st.time_input("Publication time")
            source_url = st.text_input("Original RNS URL")
            isin = st.text_input("ISIN", value="")

        source_text = st.text_area("Announcement text", height=340)
        submitted = st.form_submit_button(
            "ANALYSE AND STORE",
            type="primary",
        )

    if not submitted:
        return
    if not settings.openai_api_key:
        st.error("OPENAI_API_KEY is not configured in Railway variables.")
        return

    try:
        published_at = datetime.combine(
            publication_date,
            publication_time,
            tzinfo=LONDON,
        )
        announcement = build_manual_announcement(
            ticker=ticker,
            company=company,
            published_at=published_at,
            title=title,
            text=source_text,
            source_url=source_url,
            rns_type=rns_type,
            isin=isin,
        )
        engine = OpenAIAnalystEngine(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_output_tokens=settings.openai_max_output_tokens,
        )
        pipeline = FoundationPipeline(
            repository=intelligence_repository,
            analyst_engine=engine,
            prompt_version=settings.prompt_version,
            min_evidence_chars=settings.min_evidence_chars,
        )
        with st.status(
            "Analysing, checking and writing the versioned record…",
            expanded=True,
        ):
            persisted = pipeline.process(announcement)
        current = product_repository.get_note(
            announcement.source_id,
            public_only=False,
        )
    except AnalysisBlockedError as exc:
        st.error("Analysis blocked by deterministic quality checks.")
        st.json(exc.report.model_dump(mode="json"))
        return
    except Exception as exc:
        st.exception(exc)
        return

    if persisted.quality_status == "review":
        st.warning("Stored for owner review; excluded from the public Feed.")
    else:
        st.success("Announcement analysed and stored as publishable.")

    st.subheader("Persistence result")
    st.json(persisted.model_dump(mode="json"))
    if current:
        st.subheader("Current full record")
        st.json(current)
