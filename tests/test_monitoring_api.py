from __future__ import annotations

from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.monitoring import create_monitoring_routes
from database.monitoring import MonitoringSheetQuery
from product.monitoring import (
    MonitoringBalanceSheet,
    MonitoringDisclosure,
    MonitoringImpact,
    MonitoringMarketReaction,
    MonitoringProvenance,
    MonitoringQueryEcho,
    MonitoringResearch,
    MonitoringSheetDetail,
    MonitoringSheetPage,
    MonitoringSheetRow,
    MonitoringWhatChanged,
)


class StubMonitoringRepository:
    def __init__(self) -> None:
        self.last_query: MonitoringSheetQuery | None = None
        self.row = MonitoringSheetRow(
            source_id="spr-contract",
            ticker="SPR",
            company="Springfield Properties plc",
            market="AIM",
            isin="GB00EXAMPLE",
            published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
            rns_title="Contract Award",
            rns_type="Contracts",
            signal="GREEN",
            takeaway=(
                "£12m three-year contract signed. Guidance unchanged; margin undisclosed."
            ),
            what_changed="A £12m three-year contract was signed.",
            ai_view="Useful win, but margin remains undisclosed.",
            outlook="MAINTAINED",
            market_reaction=MonitoringMarketReaction(
                status="available",
                label="+5.0% at close",
                phase="close",
                change_pct=5.0,
            ),
            balance_sheet=MonitoringBalanceSheet(
                status="carried",
                label="Net debt",
                value="£18.2m",
                as_of_date="31 May 2026",
                source_id="spr-results",
            ),
            impact=MonitoringImpact(score=3, level="high"),
            detail_url="/api/v1/monitoring/spr-contract",
            original_source_url="https://example.invalid/spr-contract",
        )
        self.detail = MonitoringSheetDetail(
            **self.row.model_dump(),
            research=MonitoringResearch(
                verdict="£12m contract won; margin remains undisclosed",
                takeaway=self.row.takeaway,
                what_changed=MonitoringWhatChanged(
                    before="No contract was previously disclosed.",
                    today=self.row.what_changed,
                    read_through="The win is useful but not an earnings upgrade.",
                ),
                analyst_view=self.row.ai_view,
                disclosure=MonitoringDisclosure(status="partial"),
                provenance=MonitoringProvenance(
                    evidence_status="complete",
                    quality_status="publishable",
                    confidence=0.92,
                    analysis_version="aim-intelligence-analyst-3.3",
                    prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
                    model_version="recorded",
                    source_urls=[self.row.original_source_url],
                ),
            ),
        )

    def list_rows(self, query: MonitoringSheetQuery) -> MonitoringSheetPage:
        self.last_query = query
        return MonitoringSheetPage(
            generated_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
            query=MonitoringQueryEcho(
                date_from=query.date_from.isoformat(),
                date_to=query.date_to.isoformat(),
                tickers=list(query.tickers),
                search=query.search,
                signals=list(query.signals),
                outlooks=list(query.outlooks),
                sort=query.sort,
                limit=query.limit,
                offset=query.offset,
            ),
            total=1,
            count=1,
            has_more=False,
            items=[self.row],
        )

    def get_detail(self, source_id: str):
        return self.detail if source_id == "spr-contract" else None

    def health(self):
        return {
            "status": "ok",
            "schema_version": "scbb-monitoring-v1",
            "database": "sqlite",
            "publishable_records": 1,
        }


def client_and_repository() -> tuple[TestClient, StubMonitoringRepository]:
    repository = StubMonitoringRepository()
    app = Starlette(routes=create_monitoring_routes(lambda: repository))
    return TestClient(app), repository


def test_monitoring_list_endpoint_exposes_versioned_column_contract() -> None:
    client, repository = client_and_repository()

    response = client.get(
        "/api/v1/monitoring",
        params={
            "date": "2026-08-21",
            "ticker": "spr.l",
            "signal": "green",
            "outlook": "maintained",
            "sort": "impact",
            "limit": "25",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["cache-control"].startswith("public, max-age=60")
    body = response.json()
    assert body["schema_version"] == "scbb-monitoring-v1"
    assert body["items"][0]["signal"] == "GREEN"
    assert body["items"][0]["takeaway"].startswith("£12m three-year contract")
    assert body["items"][0]["what_changed"].startswith("A £12m")
    assert body["items"][0]["balance_sheet"]["status"] == "carried"
    assert body["items"][0]["detail_url"].endswith("spr-contract")

    assert repository.last_query is not None
    assert repository.last_query.tickers == ("SPR",)
    assert repository.last_query.signals == ("GREEN",)
    assert repository.last_query.outlooks == ("MAINTAINED",)
    assert repository.last_query.sort == "impact"
    assert repository.last_query.limit == 25


def test_monitoring_detail_health_schema_and_cors_preflight() -> None:
    client, _repository = client_and_repository()

    detail = client.get("/api/v1/monitoring/spr-contract")
    assert detail.status_code == 200
    assert detail.json()["takeaway"].startswith("£12m three-year contract")
    assert detail.json()["research"]["takeaway"] == detail.json()["takeaway"]
    assert detail.json()["research"]["provenance"]["quality_status"] == "publishable"
    assert detail.json()["original_source_url"].startswith("https://")

    missing = client.get("/api/v1/monitoring/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store"
    assert health.json()["status"] == "ok"

    schema = client.get("/api/v1/schemas/monitoring-sheet")
    assert schema.status_code == 200
    assert "properties" in schema.json()["list"]
    assert "takeaway" in schema.json()["list"]["$defs"]["MonitoringSheetRow"]["properties"]
    assert "properties" in schema.json()["detail"]

    options = client.options("/api/v1/monitoring")
    assert options.status_code == 204
    assert options.headers["access-control-allow-methods"] == "GET, OPTIONS"


def test_monitoring_api_rejects_invalid_queries_without_leaking_exceptions() -> None:
    client, _repository = client_and_repository()

    invalid_date = client.get("/api/v1/monitoring?date=21-08-2026")
    assert invalid_date.status_code == 400
    assert invalid_date.json() == {
        "schema_version": "scbb-monitoring-v1",
        "error": {
            "code": "INVALID_QUERY",
            "message": "date must use YYYY-MM-DD",
        },
    }

    conflicting = client.get(
        "/api/v1/monitoring?date=2026-08-21&date_from=2026-08-20"
    )
    assert conflicting.status_code == 400
    assert "cannot be combined" in conflicting.json()["error"]["message"]

    invalid_limit = client.get("/api/v1/monitoring?date=2026-08-21&limit=999")
    assert invalid_limit.status_code == 400
    assert "limit must be between" in invalid_limit.json()["error"]["message"]
