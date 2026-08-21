from datetime import date, datetime
from zoneinfo import ZoneInfo

from analyst.evidence import EvidenceUnavailableError
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import CatalogueAnnouncement
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 21)


class FakeDailySource:
    def __init__(self, *, title: str = "Trading Update") -> None:
        self.prepare_calls = 0
        self.fetch_calls = 0
        self.item = CatalogueAnnouncement(
            source_id="aim-test-daily-1",
            ticker="SPR",
            company="Springfield Properties",
            published_at=datetime(2026, 8, 21, 7, 0, tzinfo=LONDON),
            title=title,
            source_url="https://example.invalid/spr-rns",
        )

    def list_announcements(self, day):
        assert day == DAY
        return [self.item], []

    def prepare_documents(self, announcements):
        self.prepare_calls += 1
        assert [item.source_id for item in announcements] == [
            "aim-test-daily-1"
        ]
        return []

    def fetch_document(self, announcement):
        self.fetch_calls += 1
        return AnnouncementInput(
            source_id=announcement.source_id,
            ticker=announcement.ticker,
            company=announcement.company,
            published_at=announcement.published_at,
            title=announcement.title,
            text=(
                "FY expectations remain unchanged. Net debt reduced to "
                "£18.2m from £24.0m."
            ),
            source_url=announcement.source_url,
            source_urls=[announcement.source_url],
        )


class BatchDailySource(FakeDailySource):
    def __init__(self) -> None:
        super().__init__()
        self.deep_batch_size = 2
        self.prepared_batches: list[list[str]] = []
        self.items = [
            CatalogueAnnouncement(
                source_id=f"aim-test-batch-{index}",
                ticker="SPR",
                company="Springfield Properties",
                published_at=datetime(
                    2026,
                    8,
                    21,
                    7,
                    index,
                    tzinfo=LONDON,
                ),
                title="Trading Update",
                source_url=f"https://example.invalid/spr-rns-{index}",
            )
            for index in range(5)
        ]

    def list_announcements(self, day):
        assert day == DAY
        return self.items, []

    def prepare_documents(self, announcements):
        self.prepare_calls += 1
        self.prepared_batches.append(
            [item.source_id for item in announcements]
        )
        return []


class UnavailableSource(FakeDailySource):
    def fetch_document(self, announcement):
        self.fetch_calls += 1
        raise EvidenceUnavailableError("No usable evidence")


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
            impact_rationale=(
                "Lower net debt reduces financial risk while guidance is unchanged."
            ),
            impact_drivers=[
                ImpactDriver(
                    dimension="balance-sheet",
                    direction="favourable",
                    significance=3,
                    rationale="Net debt reduced to £18.2m from £24.0m.",
                )
            ],
            headline="Guidance maintained; net debt reduced",
            takeaway=(
                "The update maintains expectations while improving the "
                "financial position."
            ),
            key_facts=[
                KeyFact(
                    label="Net debt",
                    metric="net debt",
                    value="£18.2m",
                    currency="GBP",
                    basis="reported",
                    comparator="£24.0m",
                    previous_value="£24.0m",
                    comparator_type="prior-disclosure",
                )
            ],
            new_information=["Net debt reduced to £18.2m."],
            reiterated_information=["FY expectations remain unchanged."],
            what_changed=WhatChanged(
                before="Net debt was £24.0m.",
                today=(
                    "FY expectations are unchanged and net debt is £18.2m."
                ),
                read_through=(
                    "The earnings position is unchanged while financial risk "
                    "has reduced."
                ),
                coverage_status=(
                    "established" if prior_context else "building"
                ),
            ),
            analyst_view=(
                "The main new information is the lower net debt position "
                "rather than an earnings change."
            ),
            supports_case=["Lower net debt."],
            challenges_case=["No earnings upgrade."],
            watch_items=["Next net debt update."],
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=announcement.source_urls,
            confidence=0.9,
        )


def make_service(source):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    repository = IntelligenceRepository(create_session_factory(engine))
    analyst = FakeAnalyst()
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=analyst,
        prompt_version="analyst-engine-2.0",
    )
    service = DailyAIMIngestionService(
        source=source,
        repository=repository,
        pipeline=pipeline,
    )
    return service, analyst


def test_daily_service_deduplicates_before_evidence_retrieval():
    source = FakeDailySource()
    service, analyst = make_service(source)

    first = service.run(DAY)
    second = service.run(DAY)

    assert first.discovered == 1
    assert first.already_known == 0
    assert first.analysed == 1
    assert second.discovered == 1
    assert second.already_known == 1
    assert second.analysed == 0
    assert source.prepare_calls == 1
    assert source.fetch_calls == 1
    assert analyst.calls == 1


def test_relevant_announcements_are_retrieved_in_progressive_batches():
    source = BatchDailySource()
    service, analyst = make_service(source)

    result = service.run(DAY)

    assert result.discovered == 5
    assert result.analysed == 5
    assert source.prepare_calls == 3
    assert [len(batch) for batch in source.prepared_batches] == [2, 2, 1]
    assert source.fetch_calls == 5
    assert analyst.calls == 5


def test_unavailable_evidence_is_left_retryable():
    source = UnavailableSource()
    service, analyst = make_service(source)

    first = service.run(DAY)
    second = service.run(DAY)

    assert first.blocked == 1
    assert first.already_known == 0
    assert second.blocked == 1
    assert second.already_known == 0
    assert source.prepare_calls == 2
    assert analyst.calls == 0


def test_true_routine_notice_uses_no_deep_ai_call():
    source = FakeDailySource(title="Total Voting Rights")
    service, analyst = make_service(source)

    result = service.run(DAY)

    assert result.routine_persisted == 1
    assert result.analysed == 0
    assert source.prepare_calls == 0
    assert source.fetch_calls == 0
    assert analyst.calls == 0
