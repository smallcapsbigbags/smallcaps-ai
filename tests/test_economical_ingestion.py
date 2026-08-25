from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    WhatChanged,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import CatalogueAnnouncement
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 25)


class FunnelSource:
    deep_batch_size = 5

    def __init__(self, items: list[tuple[str, str, str]]) -> None:
        self.items = [
            CatalogueAnnouncement(
                source_id=source_id,
                ticker="TST",
                company="Triage Test plc",
                published_at=datetime(2026, 8, 25, 7, index, tzinfo=LONDON),
                title=title,
                source_url=f"https://example.invalid/{source_id}",
            )
            for index, (source_id, title, _text) in enumerate(items)
        ]
        self.documents = {source_id: text for source_id, _title, text in items}
        self.prepare_calls = 0
        self.fetch_calls = 0

    def list_announcements(self, day):
        assert day == DAY
        return self.items, []

    def prepare_documents(self, announcements):
        self.prepare_calls += 1
        return []

    def fetch_document(self, item):
        self.fetch_calls += 1
        return AnnouncementInput(
            source_id=item.source_id,
            ticker=item.ticker,
            company=item.company,
            published_at=item.published_at,
            title=item.title,
            text=self.documents[item.source_id],
            source_url=item.source_url,
            source_urls=[item.source_url],
        )


class FunnelAnalyst:
    model_name = "funnel-test-analyst"

    def __init__(self) -> None:
        self.calls = 0

    def analyse(self, announcement, prior_context):
        self.calls += 1
        return AnalystNote(
            source_id=announcement.source_id,
            rns_type="Results & trading" if "Trading" in announcement.title else "Contracts",
            impact_colour="amber",
            impact_score=3,
            impact_level="high",
            impact_rationale="The announcement warrants full investor analysis.",
            headline="Material announcement analysed in full",
            takeaway="The evidence was escalated through the newsroom funnel.",
            key_facts=[],
            what_changed=WhatChanged(
                before="Previous position recorded where available.",
                today="The current announcement contains a material new development.",
                read_through="The investment case requires updated monitoring.",
                coverage_status="established" if prior_context else "building",
            ),
            analyst_view="Material development. Full analysis is required before drawing a stronger conclusion.",
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=announcement.source_urls,
            confidence=0.9,
        )


def service_for(source: FunnelSource, *, max_ai_items: int = 36):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    repository = IntelligenceRepository(create_session_factory(engine))
    analyst = FunnelAnalyst()
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=analyst,
        prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
    )
    service = DailyAIMIngestionService(
        source=source,
        repository=repository,
        pipeline=pipeline,
        max_ai_items=max_ai_items,
    )
    return service, analyst, repository


def test_light_item_is_recorded_and_screened_without_full_analyst_call() -> None:
    source = FunnelSource(
        [
            (
                "light-director",
                "Director/PDMR Shareholding",
                "A non-executive director purchased shares for £20,000.",
            )
        ]
    )
    service, analyst, _repository = service_for(source)

    first = service.run(DAY)
    second = service.run(DAY)

    assert first.recorded == 1
    assert first.light_processed == 1
    assert first.full_analysed == 0
    assert first.analysed == 0
    assert analyst.calls == 0
    assert source.prepare_calls == 1
    assert source.fetch_calls == 1
    assert second.already_known == 1
    assert second.recorded == 0


def test_light_contract_escalates_to_full_when_scale_is_material() -> None:
    source = FunnelSource(
        [
            (
                "material-contract",
                "Contract Award",
                "The company has signed a £6m contract with a new customer.",
            )
        ]
    )
    service, analyst, _repository = service_for(source)

    result = service.run(DAY)

    assert result.recorded == 1
    assert result.escalated == 1
    assert result.full_selected == 1
    assert result.full_analysed == 1
    assert analyst.calls == 1
    # LIGHT retrieved the evidence once; FULL analysis reuses the cached document.
    assert source.prepare_calls == 1
    assert source.fetch_calls == 1


def test_archive_uses_no_evidence_or_full_analyst_call() -> None:
    source = FunnelSource(
        [("archive-tvr", "Total Voting Rights", "Routine share-capital denominator update.")]
    )
    service, analyst, _repository = service_for(source)

    result = service.run(DAY)

    assert result.recorded == 1
    assert result.archived == 1
    assert result.routine_persisted == 1
    assert result.full_analysed == 0
    assert source.prepare_calls == 0
    assert source.fetch_calls == 0
    assert analyst.calls == 0


def test_full_cap_records_deferred_items_without_marking_them_known() -> None:
    source = FunnelSource(
        [
            (f"full-{index}", "Trading Update", "FY guidance and cash position updated.")
            for index in range(4)
        ]
    )
    service, analyst, _repository = service_for(source, max_ai_items=3)

    first = service.run(DAY)
    second = service.run(DAY)

    assert first.recorded == 4
    assert first.full_selected == 3
    assert first.full_analysed == 3
    assert first.deferred == 1
    assert analyst.calls == 4
    assert second.already_known == 3
    assert second.recorded == 1
    assert second.full_analysed == 1
