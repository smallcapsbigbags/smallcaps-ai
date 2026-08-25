from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from analyst.models import AnnouncementInput
from analyst.triage import (
    TRIAGE_VERSION,
    TriageContext,
    triage_evidence,
    triage_metadata,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.repository import IntelligenceRepository
from database.triage_store import TriageRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import CatalogueAnnouncement
from jobs.run_triage_benchmark import run as run_triage_benchmark

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 25)


def item(title: str, *, source_id: str = "triage-test") -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id=source_id,
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 25, 7, 0, tzinfo=LONDON),
        title=title,
        source_url=f"https://example.invalid/{source_id}",
    )


def test_metadata_triage_benchmark_is_loss_averse_and_exact():
    cases = json.loads(Path("benchmarks/triage_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        decision = triage_metadata(item(case["title"], source_id=case["id"]))
        results.append((case["id"], decision.processing_level, case["expected"]))

    assert results
    assert all(actual == expected for _case_id, actual, expected in results), results
    assert len(results) == 18


def test_light_evidence_escalates_only_when_a_deterministic_trigger_is_present():
    contract = item("Contract Award")
    assert triage_evidence(
        contract,
        "A new contract worth £500,000 was signed.",
        context=TriageContext(latest_revenue_value="£100m"),
    ).processing_level == "light"
    relative = triage_evidence(
        contract,
        "A new three-year contract worth £3m was signed.",
        context=TriageContext(latest_revenue_value="£20m"),
    )
    assert relative.processing_level == "full"
    assert "10%" in relative.escalation_reason

    dealing = item("Director/PDMR Shareholding")
    small_ned = triage_evidence(
        dealing,
        "A non-executive director purchased ordinary shares for £12,000.",
    )
    assert small_ned.processing_level == "light"
    senior = triage_evidence(
        dealing,
        "The Chief Executive Officer purchased shares for £12,000.",
    )
    assert senior.processing_level == "full"
    assert "CEO/CFO" in senior.escalation_reason

    after_warning = triage_evidence(
        dealing,
        "A director purchased ordinary shares for £20,000.",
        context=TriageContext(recent_adverse_trading=True),
    )
    assert after_warning.processing_level == "full"

    repeated = triage_evidence(
        dealing,
        "A director purchased ordinary shares for £10,000.",
        context=TriageContext(recent_director_dealings=2),
    )
    assert repeated.processing_level == "full"

    ltip = item("Grant of Awards under Long-Term Incentive Plan")
    assert triage_evidence(
        ltip,
        "The company granted 500,000 nil-cost options.",
        context=TriageContext(latest_share_count_value="100m"),
    ).processing_level == "light"
    relative_ltip = triage_evidence(
        ltip,
        "The company granted 5m nil-cost options.",
        context=TriageContext(latest_share_count_value="100m"),
    )
    assert relative_ltip.processing_level == "full"
    assert "3%" in relative_ltip.escalation_reason


def test_light_screen_extracts_minimum_reprocessable_fact_sketch():
    decision = triage_evidence(
        item("Director/PDMR Shareholding"),
        "The CFO purchased £62,500 of shares, representing 0.4% of the company.",
    )
    assert {fact["kind"] for fact in decision.light_facts} >= {
        "money",
        "percent",
        "role",
    }

    options = triage_evidence(
        item("Grant of Awards under Long-Term Incentive Plan"),
        "The company granted 5m nil-cost options.",
        context=TriageContext(latest_share_count_value="100m"),
    )
    assert any(fact["kind"] == "securities" for fact in options.light_facts)


def test_full_triage_benchmark_passes_and_reports_analyst_savings():
    result = run_triage_benchmark(
        Path("benchmarks/triage_cases.json"),
        Path("benchmarks/triage_evidence_cases.json"),
    )
    assert result["passed"] is True
    assert result["failure_count"] == 0
    assert result["metadata_cases"] == 18
    assert result["evidence_cases"] >= 14
    assert result["projected_full_analyst_calls"] < result["baseline_full_analyst_calls"]
    assert result["estimated_full_analyst_call_reduction_pct"] > 0


class StubPipeline:
    prompt_version = "analyst-engine-3.3-scbb-monitoring-sheet"

    def __init__(self) -> None:
        self.calls = 0

    def process(self, announcement):
        self.calls += 1
        return SimpleNamespace(source_id=announcement.source_id, quality_status="publishable")


class OneItemSource:
    deep_batch_size = 5

    def __init__(self, title: str, text: str) -> None:
        self.catalogue = item(title, source_id="daily-light")
        self.text = text
        self.prepare_calls = 0
        self.fetch_calls = 0

    def list_announcements(self, day):
        assert day == DAY
        return [self.catalogue], []

    def prepare_documents(self, announcements):
        self.prepare_calls += 1
        return []

    def fetch_document(self, announcement):
        self.fetch_calls += 1
        return AnnouncementInput(
            source_id=announcement.source_id,
            ticker=announcement.ticker,
            company=announcement.company,
            published_at=announcement.published_at,
            title=announcement.title,
            text=self.text,
            source_url=announcement.source_url,
            source_urls=[announcement.source_url],
            evidence_status="complete",
        )


def service_for(source: OneItemSource):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)
    pipeline = StubPipeline()
    return (
        DailyAIMIngestionService(source=source, repository=repository, pipeline=pipeline),
        TriageRepository(factory),
        pipeline,
    )


def test_light_item_is_recorded_screened_once_and_skips_full_analyst():
    source = OneItemSource(
        "Contract Award",
        "A £500,000 contract was signed. Margin was not disclosed.",
    )
    service, triage_repo, pipeline = service_for(source)

    first = service.run(DAY)
    second = service.run(DAY)

    assert first.light_processed == 1
    assert first.analyst_calls_avoided == 1
    assert first.analysed == 0
    assert second.already_known == 1
    assert source.fetch_calls == 1
    assert pipeline.calls == 0

    row = triage_repo.get("daily-light")
    assert row is not None
    assert row.status == "complete"
    assert row.processing_level == "light"
    assert row.triage_version == TRIAGE_VERSION
    assert row.source_hash
    assert row.evidence_hash
    assert row.evidence_source_urls == ["https://example.invalid/daily-light"]


def test_light_item_escalates_to_full_without_a_second_evidence_fetch():
    source = OneItemSource(
        "Contract Award",
        "A material contract worth £3.2m was signed.",
    )
    service, triage_repo, pipeline = service_for(source)

    result = service.run(DAY)

    assert result.escalated_to_full == 1
    assert result.analysed == 1
    assert result.light_processed == 0
    assert source.fetch_calls == 1
    assert pipeline.calls == 1
    row = triage_repo.get("daily-light")
    assert row is not None
    assert row.status == "complete"
    assert row.processing_level == "full"
    assert row.escalated is True
