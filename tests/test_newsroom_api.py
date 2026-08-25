from __future__ import annotations

from datetime import date, datetime, time, timezone

from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.newsroom import create_newsroom_routes
from product.newsroom import NewsroomArticle, NewsroomClaim, NewsroomEdition, NewsroomEvidenceRef


class StubNewsroomRepository:
    def __init__(self) -> None:
        self.last_day: date | None = None
        self.last_state: str | None = None
        self.last_cutoff: time | None = None

    def get_edition(self, day: date, *, edition_state: str | None = None, cutoff: time | None = None) -> NewsroomEdition:
        self.last_day = day
        self.last_state = edition_state
        self.last_cutoff = cutoff
        ref = NewsroomEvidenceRef(
            source_id="spr-update",
            source_url="https://example.com/spr-update",
            published_at="2026-08-25T07:10:00+01:00",
            field_path="facts",
            label="Net debt",
        )
        article = NewsroomArticle(
            story_key="SPR:trading:spr-update",
            story_family="trading",
            ticker="SPR",
            company="Springfield Properties plc",
            bucket="lead",
            impact_score=4,
            signal="GREEN",
            outlook="MAINTAINED",
            headline="Springfield cuts net debt again",
            news=NewsroomClaim(kind="news", text="Net debt fell again.", provenance=[ref]),
            view=NewsroomClaim(kind="view", text="Good balance-sheet progress.", provenance=[ref]),
            source_ids=["spr-update"],
            source_urls=["https://example.com/spr-update"],
            copydesk_status="pass",
        )
        return NewsroomEdition(
            generated_at=datetime(2026, 8, 25, 7, 55, tzinfo=timezone.utc),
            date=day.isoformat(),
            edition_state=edition_state or "morning_note",
            cutoff=(cutoff or time(8, 0)).strftime("%H:%M"),
            source_editor_schema="aim-daily-editor-v2",
            source_editor_version="aim-daily-editor-2.0",
            screened_candidate_count=8,
            selected_story_count=4,
            published_article_count=4,
            withheld_story_count=0,
            other_analysed_count=4,
            lead=article,
        )


def _client() -> tuple[TestClient, StubNewsroomRepository]:
    repository = StubNewsroomRepository()
    app = Starlette(routes=create_newsroom_routes(lambda: repository))
    return TestClient(app), repository


def test_newsroom_endpoint_is_json_only_and_versioned() -> None:
    client, repository = _client()
    response = client.get("/api/v1/aim-daily/newsroom?date=2026-08-25&state=morning_note")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public, max-age=60")
    body = response.json()
    assert body["schema_version"] == "aim-daily-newsroom-v1"
    assert body["newsroom_version"] == "aim-daily-newsroom-1.0"
    assert body["lead"]["headline"] == "Springfield cuts net debt again"
    assert body["lead"]["copydesk_status"] == "pass"
    assert repository.last_day == date(2026, 8, 25)
    assert repository.last_state == "morning_note"
    assert repository.last_cutoff is None


def test_newsroom_schema_is_strict() -> None:
    client, _repository = _client()
    response = client.get("/api/v1/schemas/aim-daily-newsroom")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "aim-daily-newsroom-v1"
    assert body["edition"]["additionalProperties"] is False
    assert "copydesk_status" in str(body["edition"])


def test_newsroom_rejects_conflicting_state_and_cutoff() -> None:
    client, _repository = _client()
    response = client.get("/api/v1/aim-daily/newsroom?date=2026-08-25&state=morning_note&cutoff=08:15")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"
    assert "cannot be combined" in response.json()["error"]["message"]
