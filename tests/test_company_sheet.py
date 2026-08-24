from __future__ import annotations

from database.company_sheet import CompanySheetRepository
from database.db import create_database_engine, create_session_factory, init_database
from jobs.seed_launch_preview import seed as seed_launch_preview
from jobs.seed_pass1_preview import seed as seed_pass1_preview
from product.company_sheet import COMPANY_SHEET_SCHEMA_VERSION


def seeded_repository(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'company-sheet.db'}"
    seed_launch_preview(database_url)
    seed_pass1_preview(database_url)
    engine = create_database_engine(database_url)
    init_database(engine)
    return engine, CompanySheetRepository(create_session_factory(engine))


def test_company_sheet_composes_current_view_memory_and_history(tmp_path) -> None:
    engine, repository = seeded_repository(tmp_path)
    try:
        company = repository.get_company("spr.l")
    finally:
        engine.dispose()

    assert company is not None
    assert company.schema_version == COMPANY_SHEET_SCHEMA_VERSION
    assert company.ticker == "SPR"
    assert company.company == "Springfield Properties plc"
    assert company.coverage.announcement_count == 2
    assert company.coverage.status == "building"

    assert company.current_position is not None
    assert company.current_position.source_id == "spr-preview-buyback"
    assert company.current_position.signal == "GREEN"
    assert company.current_position.impact.score == 4
    assert company.current_position.balance_sheet.status == "carried"
    assert company.current_position.balance_sheet.value == "£24.0m"

    assert any(item.metric == "adjusted profit" for item in company.guidance)
    assert any(item.metric == "net debt" for item in company.metrics)
    assert len(company.metrics) >= 3
    assert len(company.open_management_claims) == 2
    assert any("cash amount" in item.item.lower() for item in company.disclosure_gaps)
    assert [item.source_id for item in company.history] == [
        "spr-preview-buyback",
        "spr-preview-prior",
    ]


def test_sparse_company_does_not_invent_guidance_or_kpis(tmp_path) -> None:
    engine, repository = seeded_repository(tmp_path)
    try:
        company = repository.get_company("TRLS")
    finally:
        engine.dispose()

    assert company is not None
    assert company.current_position is not None
    assert company.current_position.signal == "RED"
    assert company.current_position.impact.score == 5
    assert company.guidance == []
    assert company.metrics == []
    assert company.open_management_claims == []
    assert len(company.history) == 1


def test_unknown_company_is_not_exposed(tmp_path) -> None:
    engine, repository = seeded_repository(tmp_path)
    try:
        assert repository.get_company("NOTREAL") is None
    finally:
        engine.dispose()
