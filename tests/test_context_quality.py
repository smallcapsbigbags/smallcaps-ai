from datetime import datetime, timedelta, timezone

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    QualityFlag,
    QualityReport,
    WhatChanged,
)
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.repository import IntelligenceRepository


def make_announcement(source_id: str, published_at: datetime) -> AnnouncementInput:
    return AnnouncementInput(
        source_id=source_id,
        ticker="ABC",
        company="ABC plc",
        published_at=published_at,
        title="Trading Update",
        text="Revenue was £10m and net debt was £2m for the period.",
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
    )


def make_note(source_id: str) -> AnalystNote:
    return AnalystNote(
        source_id=source_id,
        rns_type="Results & trading",
        impact_colour="grey",
        impact_score=1,
        impact_level="low",
        impact_rationale="No meaningful change from the disclosed position.",
        headline="Trading broadly unchanged",
        takeaway="The announcement does not change the current earnings view.",
        what_changed=WhatChanged(
            before="Coverage is building.",
            today="Revenue and debt were reported.",
            read_through="No meaningful directional change was identified.",
        ),
        analyst_view="The update is mainly confirmatory.",
        disclosure_assessment=DisclosureAssessment(status="complete"),
        source_references=[f"https://example.invalid/{source_id}"],
        confidence=0.9,
    )


def test_review_required_analysis_does_not_enter_company_context():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    repository = IntelligenceRepository(create_session_factory(engine))
    now = datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)

    publishable = make_announcement("published", now)
    repository.save_analysis(
        publishable,
        make_note("published"),
        prompt_version="analyst-engine-2.0",
        model_version="test",
        quality_report=QualityReport(status="publishable"),
    )

    review = make_announcement("review", now + timedelta(minutes=1))
    repository.save_analysis(
        review,
        make_note("review"),
        prompt_version="analyst-engine-2.0",
        model_version="test",
        quality_report=QualityReport(
            status="review",
            flags=[
                QualityFlag(
                    code="PARTIAL_EVIDENCE",
                    severity="review",
                    message="Owner review required.",
                )
            ],
        ),
    )

    context = repository.load_prior_context(
        "ABC", before=now + timedelta(days=1)
    )

    assert [item["source_id"] for item in context] == ["published"]
