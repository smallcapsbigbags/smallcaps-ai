from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from analyst.models import AnnouncementInput
from database.db import create_database_engine, create_session_factory, init_database
from database.queries import known_source_ids
from database.repository import IntelligenceRepository
from database.triage import TriageRepository
from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.triage import TriageDecision

LONDON = ZoneInfo("Europe/London")


def catalogue(source_id: str, title: str) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id=source_id,
        ticker="TST",
        company="Triage Test plc",
        published_at=datetime(2026, 8, 25, 7, 0, tzinfo=LONDON),
        title=title,
        source_url=f"https://example.invalid/{source_id}",
    )


def document(item: CatalogueAnnouncement, text: str) -> AnnouncementInput:
    return AnnouncementInput(
        source_id=item.source_id,
        ticker=item.ticker,
        company=item.company,
        published_at=item.published_at,
        title=item.title,
        text=text,
        source_url=item.source_url,
        source_urls=[item.source_url],
    )


def repositories():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    return IntelligenceRepository(factory), TriageRepository(factory)


def test_archive_and_final_light_are_terminal_without_full_analyst_run() -> None:
    intelligence, triage = repositories()
    archive = catalogue("archive-one", "Total Voting Rights")
    light = catalogue("light-one", "Director/PDMR Shareholding")

    triage.record_catalogue(
        archive,
        TriageDecision("ARCHIVE", "ARCHIVE", "Routine.", 5),
    )
    triage.record_catalogue(
        light,
        TriageDecision("LIGHT", "LIGHT", "Screen.", 45),
    )
    triage.record_document(
        document(light, "A non-executive director purchased shares for £15,000."),
        TriageDecision(
            "LIGHT",
            "LIGHT",
            "Screen.",
            45,
            light_facts=[{"kind": "money", "value": "£15,000"}],
        ),
    )

    assert known_source_ids(intelligence, [archive.source_id, light.source_id]) == {
        archive.source_id,
        light.source_id,
    }


def test_full_and_escalated_pending_rows_remain_retryable() -> None:
    intelligence, triage = repositories()
    full = catalogue("full-one", "Trading Update")
    escalated = catalogue("escalated-one", "Contract Award")

    triage.record_catalogue(
        full,
        TriageDecision("FULL", "FULL", "High signal.", 90),
    )
    triage.record_catalogue(
        escalated,
        TriageDecision("LIGHT", "LIGHT", "Screen.", 45),
    )
    triage.record_document(
        document(escalated, "An £8m contract has been awarded."),
        TriageDecision(
            "LIGHT",
            "FULL",
            "Screen.",
            85,
            escalated=True,
            escalation_reason="Material relative to revenue.",
        ),
    )

    assert known_source_ids(intelligence, [full.source_id, escalated.source_id]) == set()


def test_catalogue_shell_preserves_source_provenance_for_reprocessing() -> None:
    intelligence, triage = repositories()
    item = catalogue("full-provenance", "Profit Warning")
    triage.record_catalogue(
        item,
        TriageDecision("FULL", "FULL", "High signal.", 100),
    )

    current = intelligence.get_current_analysis(item.source_id)
    assert current is None
    # The absence of an AnalystRun is deliberate; known_source_ids must therefore
    # keep the metadata shell retryable until full evidence/analysis succeeds.
    assert known_source_ids(intelligence, [item.source_id]) == set()
