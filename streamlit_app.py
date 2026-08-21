from __future__ import annotations

import hmac
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from analyst.analyzer import OpenAIAnalystEngine
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.repository import IntelligenceRepository
from ingestion.manual import build_manual_announcement
from pipeline import AnalysisBlockedError, FoundationPipeline
from settings import Settings

load_dotenv()
LONDON = ZoneInfo("Europe/London")

st.set_page_config(
    page_title="Smallcaps.ai · Analyst QA",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def get_repository(database_url: str) -> IntelligenceRepository:
    engine = create_database_engine(database_url)
    init_database(engine)
    return IntelligenceRepository(create_session_factory(engine))


def require_admin_access(settings: Settings) -> None:
    """Protect the operator console whenever an admin password is configured."""

    if not settings.app_admin_password:
        st.warning(
            "APP_ADMIN_PASSWORD is not configured. Do not expose this operator "
            "console publicly until the password is set."
        )
        return
    if st.session_state.get("admin_access_granted"):
        return

    st.title("smallcaps.ai")
    st.caption("Private Analyst QA")
    with st.form("admin-access", clear_on_submit=True):
        supplied = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("UNLOCK")
    if submitted and hmac.compare_digest(
        supplied, settings.app_admin_password
    ):
        st.session_state["admin_access_granted"] = True
        st.rerun()
    if submitted:
        st.error("That access code is not valid.")
    st.stop()


def main() -> None:
    settings = Settings.from_env()
    require_admin_access(settings)
    repository = get_repository(settings.database_url)

    st.title("smallcaps.ai")
    st.caption("AIM Intelligence · Analyst Engine 2.0 QA console")
    st.info(
        "Manual ingestion is a QA/recovery path. The daily product uses "
        "Investegate discovery → OpenAI evidence retrieval → Analyst Engine."
    )

    with st.form("manual-rns"):
        c1, c2 = st.columns(2)
        with c1:
            ticker = st.text_input("Ticker", placeholder="IHC")
            company = st.text_input(
                "Company", placeholder="Inspiration Healthcare Group"
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
            "ANALYSE AND STORE", type="primary"
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
            repository=repository,
            analyst_engine=engine,
            prompt_version=settings.prompt_version,
            min_evidence_chars=settings.min_evidence_chars,
        )
        with st.status(
            "Analysing, checking and writing the versioned record…",
            expanded=True,
        ):
            persisted = pipeline.process(announcement)
        current = repository.get_current_analysis(
            announcement.source_id
        )
    except AnalysisBlockedError as exc:
        st.error("Analysis blocked by deterministic quality checks.")
        st.json(exc.report.model_dump(mode="json"))
        return
    except Exception as exc:
        st.exception(exc)
        return

    if persisted.quality_status == "review":
        st.warning("Stored, but marked for owner review before publication.")
    else:
        st.success("Announcement analysed and stored as publishable.")

    st.subheader("Persistence result")
    st.json(persisted.model_dump(mode="json"))
    if current:
        st.subheader("Current database record")
        st.json(current)


if __name__ == "__main__":
    main()
