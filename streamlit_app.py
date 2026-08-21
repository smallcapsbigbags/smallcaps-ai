from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository
from database.product import ProductRepository
from database.repository import IntelligenceRepository
from settings import Settings
from ui.admin import render_admin
from ui.common import inject_styles, query_value, require_beta_access
from ui.company import render_company
from ui.feed import render_feed
from ui.note import render_note

load_dotenv()
st.set_page_config(page_title="Smallcaps.ai · AIM Intelligence", page_icon="◉", layout="wide", initial_sidebar_state="collapsed")


@st.cache_resource
def get_repositories(database_url: str) -> tuple[IntelligenceRepository, ProductRepository, OperationsRepository]:
    engine = create_database_engine(database_url)
    init_database(engine)
    factory = create_session_factory(engine)
    return IntelligenceRepository(factory), ProductRepository(factory), OperationsRepository(factory)


def main() -> None:
    settings = Settings.from_env()
    inject_styles()
    errors, _warnings = settings.runtime_issues("web")
    if errors:
        st.error("Runtime configuration is incomplete.")
        for error in errors:
            st.code(error, language=None)
        st.stop()
    require_beta_access(settings.app_beta_password, enabled=settings.private_beta_mode)
    intelligence_repository, product_repository, operations_repository = get_repositories(settings.database_url)
    view = query_value("view", "feed").lower()
    if view == "note":
        render_note(product_repository, query_value("source_id"))
        return
    if view == "company":
        render_company(product_repository, query_value("ticker"), default_watchlist=settings.default_watchlist)
        return
    if view == "admin":
        render_admin(settings, intelligence_repository, product_repository, operations_repository)
        return
    render_feed(product_repository, settings)


if __name__ == "__main__":
    main()
