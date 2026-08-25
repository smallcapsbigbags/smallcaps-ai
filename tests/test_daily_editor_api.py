from __future__ import annotations

from datetime import date, datetime, time, timezone

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.daily_editor import create_daily_editor_routes
from product.daily_editor import DailyEditorPage, DailyEditorStory


class StubDailyEditorRepository:
    def __init__(self) -> None:
        self.last_day: date | None = None
        self.last_cutoff: time | None = None

    def get_edition(self, day: date, *, cutoff: time) -> DailyEditorPage:
        self.last_day = day
        self.last_cutoff = cutoff
        story = DailyEditorStory(
            primary_source_id="spr-update",
            source_ids=["spr-update"],
            ticker="SPR",
            company="Springfield Properties plc",
            published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
            bucket="lead",
            priority_score=67,
            ranking_reasons=["Impact 4/5 contributes 40 points."],
            rns_types=["Results & trading"],
            signal="GREEN",
            outlook="UPGRADED",
            impact_score=4,
            editorial_headline="Guidance upgraded as debt falls",
            why_it_matters="A genuine earnings and balance-sheet improvement.",
            what_changed="Guidance moved up and net debt fell.",
            source_urls=["https://example.invalid/spr-update"],
        )
        return DailyEditorPage(
            generated_at=datetime(2026, 8, 21, 11, 30, tzinfo=timezone.utc),
            date=day.isoformat(),
            cutoff=cutoff.strftime("%H:%M"),
            quiet_morning=False,
            candidate_count=1,
            published_story_count=1,
            other_analysed_count=0,
            lead=story,
        )


def client_and_repository() -> tuple[TestClient, StubDailyEditorRepository]:
    repository = StubDailyEditorRepository()
    app = Starlette(routes=create_daily_editor_routes(lambda: repository))
    return TestClient(app), repository


def test_aim_daily_endpoint_exposes_versioned_json_only_contract() -> None:
    client, repository = client_and_repository()

    response = client.get(
        "/api/v1/aim-daily",
        params={"date": "2026-08-21", "cutoff": "11:30"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["cache-control"].startswith("public, max-age=60")
    body = response.json()
    assert body["schema_version"] == "aim-daily-editor-v1"
    assert body["editor_version"] == "aim-daily-editor-1.0"
    assert body["lead"]["primary_source_id"] == "spr-update"
    assert body["lead"]["editorial_headline"] == "Guidance upgraded as debt falls"
    assert repository.last_day == date(2026, 8, 21)
    assert repository.last_cutoff == time(11, 30)


def test_aim_daily_schema_endpoint_is_strict_and_versioned() -> None:
    client, _repository = client_and_repository()

    response = client.get("/api/v1/schemas/aim-daily-editor")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "aim-daily-editor-v1"
    assert body["edition"]["additionalProperties"] is False
    assert "lead" in body["edition"]["properties"]
    assert "other_analysed_count" in body["edition"]["properties"]


def test_aim_daily_rejects_invalid_date_and_cutoff_without_exception_leakage() -> None:
    client, _repository = client_and_repository()

    bad_date = client.get("/api/v1/aim-daily?date=21-08-2026")
    assert bad_date.status_code == 400
    assert bad_date.json() == {
        "schema_version": "aim-daily-editor-v1",
        "error": {
            "code": "INVALID_QUERY",
            "message": "date must use YYYY-MM-DD",
        },
    }

    bad_cutoff = client.get("/api/v1/aim-daily?date=2026-08-21&cutoff=11:30:45")
    assert bad_cutoff.status_code == 400
    assert bad_cutoff.json()["error"]["code"] == "INVALID_QUERY"
    assert bad_cutoff.json()["error"]["message"] == "cutoff must use HH:MM"

    midnight = client.get("/api/v1/aim-daily?date=2026-08-21&cutoff=00:00")
    assert midnight.status_code == 400
    assert "after 00:00" in midnight.json()["error"]["message"]
