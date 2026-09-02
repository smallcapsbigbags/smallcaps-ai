from __future__ import annotations

import pytest

from database.company_sheet import CompanySheetRepository
from database.db import create_database_engine, create_session_factory, init_database
from jobs.seed_pass3_kpi_preview import seed as seed_pass3_kpi_preview


def test_company_sheet_publishes_only_like_for_like_source_linked_kpi_trend(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pass3-kpi.db'}"
    seed_pass3_kpi_preview(database_url)
    engine = create_database_engine(database_url)
    init_database(engine)
    try:
        sheet = CompanySheetRepository(create_session_factory(engine)).get_company("KPI")
    finally:
        engine.dispose()

    assert sheet is not None
    assert len(sheet.metrics) == 1
    revenue = sheet.metrics[0]

    assert revenue.identity == "revenue"
    assert revenue.label == "Revenue"
    assert revenue.period_family == "FY"
    assert revenue.period_type == "duration"
    assert revenue.unit_family == "currency"
    assert revenue.currency == "GBP"
    assert revenue.latest_value == "£28,500k"
    assert revenue.previous_value == "£24.0m"
    assert revenue.change_direction == "up"
    assert revenue.change_percent == pytest.approx(18.75)

    assert [point.source_id for point in revenue.trend_points] == [
        "kpi-fy23-results",
        "kpi-fy24-results",
        "kpi-fy25-results",
    ]
    assert [point.comparable_value_numeric for point in revenue.trend_points] == [
        20_000_000.0,
        24_000_000.0,
        28_500_000.0,
    ]
    assert all(point.source_url.startswith("https://") for point in revenue.trend_points)

    integrity = revenue.integrity
    assert integrity.version == "kpi-integrity-v1"
    assert integrity.status == "comparable"
    assert integrity.provenance_complete is True
    assert integrity.total_points == 4
    assert integrity.selected_points == 3
    assert integrity.comparable_points == 3
    assert integrity.source_count == 3
    assert integrity.suppressed_points == 1
    assert integrity.suppressed_series == 1
    assert integrity.warnings == ["INCOMPATIBLE_PERIOD"]

    assert all(point.period_family == "FY" for point in revenue.trend_points)
    assert all(point.basis == "reported" for point in revenue.trend_points)
    assert all(point.currency == "GBP" for point in revenue.trend_points)
