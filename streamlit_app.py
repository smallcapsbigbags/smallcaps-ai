from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from analyst.analyzer import OpenAIAnalystEngine
from database.db import create_database_engine, create_session_factory, init_database
from database.repository import IntelligenceRepository
from ingestion.manual import build_manual_announcement
from pipeline import FoundationPipeline
from settings import Settings

load_dotenv()
LONDON = ZoneInfo("Europe/London")

st.set_page_config(
    page_title="Smallcaps.ai · Foundation Console",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def get_repository(database_url: str) -> IntelligenceRepository:
    engine = create_database_engine(database_url)
    init_database(engine)
    return IntelligenceRepository(create_session_factory(engine))


def main() -> None:
    settings = Settings.from_env()
    repository = get_repository(settings.database_url)

    st.title("smallcaps.ai")
    st.caption("AIM Intelligence · Pass 1 private foundation console")
    st.info(
        "This branch proves the permanent pipeline: source → company context → "
        "structured analysis → deterministic guardrails → versioned database record."
    )

    with st.form("manual-rns"):
        c1, c2 = st.columns(2)
        with c1:
            ticker = st.text_input("Ticker", placeholder="IHC")
            company = st.text_input("Company", placeholder="Inspiration Healthcare Group")
            title = st.text_input("Announcement title", placeholder="Grant of awards under LTIP")
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
        submitted = st.form_submit_button("ANALYSE AND STORE", type="primary")

    if not submitted:
        return
    if not settings.openai_api_key:
        st.error("OPENAI_API_KEY is not configured. Add it to Railway variables.")
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
        )
        pipeline = FoundationPipeline(
            repository=repository,
            analyst_engine=engine,
            prompt_version=settings.prompt_version,
        )
        with st.status("Analysing and writing the versioned record…", expanded=True):
            persisted = pipeline.process(announcement)
        current = repository.get_current_analysis(announcement.source_id)
    except Exception as exc:
        st.exception(exc)
        return

    st.success("Announcement analysed and stored.")
    st.json(persisted.model_dump(mode="json"))
    if current:
        st.subheader("Current database record")
        st.json(current)


if __name__ == "__main__":
    main()
