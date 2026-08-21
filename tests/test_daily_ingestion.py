from datetime import date, datetime
from zoneinfo import ZoneInfo

from analyst.models import AnalystNote, AnnouncementInput, WhatChanged
from database.db import create_database_engine, create_session_factory, init_database
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import CatalogueAnnouncement
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")


class FakeDailySource:
    def __init__(self) -> None:
        self.prepare_calls = 0
        self.item = CatalogueAnnouncement(
            source_id="aim-test-daily-1",
            ticker="SPR",
            company="Springfield Properties",
            published_at=datetime(2026, 8, 21, 7, 0, tzinfo=LONDON),
            title="Trading Update",
            source_url="https://example.invalid/spr-rns",
        )

    def list_announcements(self, day):
        assert day == date(2026, 8, 21)
        return [self.item], []

    def prepare_documents(self, announcements):
        self.prepare_calls += 1
        assert [item.source_id for item in announcements] == ["aim-test-daily-1"]
        return []

    def fetch_document(self, announcement):
        return AnnouncementInput(
            source_id=announcement.source_id,
            ticker=announcement.ticker,
            company=announcement.company,
            published_at=announcement.published_at,
            title=announcement.title,
            text="FY expectations remain unchanged. Net debt reduced to £18.2m.",
            source_url=announcement.source_url,
        )


class FakeAnalyst:
    model_name = "recorded-daily-test"

    def __init__(self) -> None:
        self.calls = 0

    def analyse(self, announcement, prior_context):
        self.calls += 1
        return AnalystNote(
            source_id=announcement.source_id,
            rns_type="Results & trading",
            impact_colour="green",
            impact_score=3,
            impact_level="high",
            headline="Guidance maintained; net debt reduced",
            takeaway="The update maintains expectations while improving the financial position.",
            what_changed=WhatChanged(
                before="Coverage initiated.",
                today="FY expectations are unchanged and net debt is £18.2m.",
                read_through="The earnings position is unchanged while financial risk has reduced.",
                coverage_status="building",
            ),
            analyst_view="The main new information is the lower net debt position rather than an earnings change.",
            supports_case=["Lower net debt."],
            challenges_case=["No earnings upgrade."],
            watch_items=["Next net debt update."],
        )


def test_daily_service_deduplicates_before_evidence_retrieval():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    repository = IntelligenceRepository(create_session_factory(engine))
    analyst = FakeAnalyst()
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=analyst,
        prompt_version="test-prompt",
    )
    source = FakeDailySource()
    service = DailyAIMIngestionService(
        source=source,
        repository=repository,
        pipeline=pipeline,
    )

    first = service.run(date(2026, 8, 21))
    second = service.run(date(2026, 8, 21))

    assert first.discovered == 1
    assert first.already_known == 0
    assert first.analysed == 1
    assert second.discovered == 1
    assert second.already_known == 1
    assert second.analysed == 0
    assert source.prepare_calls == 1
    assert analyst.calls == 1
