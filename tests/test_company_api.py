from __future__ import annotations

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.company import create_company_routes
from database.company_sheet import CompanySheetRepository
from database.db import create_database_engine, create_session_factory, init_database
from jobs.seed_launch_preview import seed as seed_launch_preview
from jobs.seed_pass1_preview import seed as seed_pass1_preview


def seeded_repository(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'company-api.db'}"
    seed_launch_preview(database_url)
    seed_pass1_preview(database_url)
    engine = create_database_engine(database_url)
    init_database(engine)
    return engine, CompanySheetRepository(create_session_factory(engine))


def test_company_api_returns_strict_public_sheet(tmp_path) -> None:
    engine, repository = seeded_repository(tmp_path)
    try:
        app = Starlette(routes=create_company_routes(lambda: repository))
        client = TestClient(app)
        response = client.get("/api/v1/company/SPR")
    finally:
        engine.dispose()

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "max-age=60" in response.headers["cache-control"]
    payload = response.json()
    assert payload["schema_version"] == "scbb-company-v1"
    assert payload["ticker"] == "SPR"
    assert payload["current_position"]["schema_version"] == "scbb-monitoring-v1"
    assert payload["history"][0]["detail_url"].startswith("/api/v1/monitoring/")

    assert payload["metrics"]
    metric = payload["metrics"][0]
    assert metric["identity"]
    assert metric["latest_source_id"]
    assert metric["latest_source_url"]
    assert isinstance(metric["trend_points"], list)
    assert metric["integrity"]["version"] == "kpi-integrity-v1"
    assert metric["integrity"]["identity"] == metric["identity"]
    assert metric["integrity"]["selected_points"] >= 1


def test_company_api_hides_unknown_coverage_and_exposes_schema(tmp_path) -> None:
    engine, repository = seeded_repository(tmp_path)
    try:
        app = Starlette(routes=create_company_routes(lambda: repository))
        client = TestClient(app)
        missing = client.get("/api/v1/company/NOTREAL")
        schema = client.get("/api/v1/schemas/company-sheet")
    finally:
        engine.dispose()

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert schema.status_code == 200
    payload = schema.json()
    assert payload["schema_version"] == "scbb-company-v1"
    assert payload["company"]["additionalProperties"] is False

    definitions = payload["company"]["$defs"]
    metric_series = definitions["CompanyMetricSeries"]["properties"]
    metric_point = definitions["CompanyMetricPoint"]["properties"]
    integrity = definitions["CompanyMetricIntegrity"]["properties"]
    assert "identity" in metric_series
    assert "trend_points" in metric_series
    assert "integrity" in metric_series
    assert "comparable_value_numeric" in metric_point
    assert "provenance_complete" in integrity
