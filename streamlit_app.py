from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from database.company_intelligence import CompanyIntelligenceRepository
from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository
from database.product import ProductRepository
from database.publication_safety import reconcile_publication_safety
from database.repository import IntelligenceRepository
from settings import Settings
from ui.admin import render_admin
from ui.common import (
    inject_styles,
    log_public_exception,
    query_value,
    render_service_error,
    require_beta_access,
)
from ui.company import render_company
from ui.feed import render_feed
from ui.note import render_note

load_dotenv()
st.set_page_config(
    page_title="Smallcaps.ai · AIM Intelligence",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def get_repositories(
    database_url: str,
) -> tuple[
    IntelligenceRepository,
    ProductRepository,
    CompanyIntelligenceRepository,
    OperationsRepository,
]:
    engine = create_database_engine(database_url)
    init_database(engine)
    factory = create_session_factory(engine)
    safety = reconcile_publication_safety(factory, corrected_by="web-startup")
    if safety.moved_to_review:
        print(
            "[publication-safety] moved_to_review="
            f"{safety.moved_to_review} source_ids={','.join(safety.source_ids)}",
            flush=True,
        )
    return (
        IntelligenceRepository(factory),
        ProductRepository(factory),
        CompanyIntelligenceRepository(factory),
        OperationsRepository(factory),
    )


def _render_public_exception(exc: BaseException) -> None:
    """Log the full failure and show only a safe incident reference publicly."""

    reference = log_public_exception(exc)
    render_service_error(reference=reference)


def main() -> None:
    inject_styles()
    try:
        settings = Settings.from_env()
    except Exception as exc:
        _render_public_exception(exc)
        return

    errors, _warnings = settings.runtime_issues("web")
    if errors:
        for error in errors:
            print(f"[runtime-error] {error}", flush=True)
        render_service_error(reference="runtime-configuration")
        return

    require_beta_access(
        settings.app_beta_password,
        enabled=settings.private_beta_mode,
    )

    try:
        (
            intelligence_repository,
            product_repository,
            company_intelligence_repository,
            operations_repository,
        ) = get_repositories(settings.database_url)
    except Exception as exc:
        _render_public_exception(exc)
        return

    view = query_value("view", "feed").lower()
    try:
        if view == "note":
            render_note(product_repository, query_value("source_id"))
            return
        if view == "company":
            render_company(
                product_repository,
                company_intelligence_repository,
                query_value("ticker"),
                default_watchlist=settings.default_watchlist,
            )
            return
        if view == "admin":
            render_admin(
                settings,
                intelligence_repository,
                product_repository,
                operations_repository,
            )
            return
        render_feed(product_repository, settings)
    except Exception as exc:
        _render_public_exception(exc)


if __name__ == "__main__":
    main()
