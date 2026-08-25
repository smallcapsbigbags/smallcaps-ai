from __future__ import annotations

from datetime import date, datetime, time, timezone

from database.daily_editor import DailyEditorRepository
from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow


def _add_run(session, *, company: CompanyRow, source_id: str, model_version: str, quality: str = "publishable", hour: int = 7) -> None:
    announcement = AnnouncementRow(
        company_id=company.id,
        source_id=source_id,
        published_at=datetime(2026, 8, 21, hour, 0, tzinfo=timezone.utc),
        headline="Trading Update" if model_version != "deterministic-metadata" else "Total Voting Rights",
        announcement_type="Results & trading" if model_version != "deterministic-metadata" else "Share capital",
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
        source_note="test",
        evidence_status="complete",
        raw_text="FY expectations changed and net debt improved.",
        categories=[],
    )
    session.add(announcement)
    session.flush()
    session.add(
        AnalystRunRow(
            announcement_id=announcement.id,
            impact_colour="green",
            impact_score=4 if model_version != "deterministic-metadata" else 1,
            impact_level="high" if model_version != "deterministic-metadata" else "low",
            impact_rationale="Decision-useful change." if model_version != "deterministic-metadata" else "Administrative.",
            impact_drivers=[],
            headline="Guidance improves as debt falls" if model_version != "deterministic-metadata" else "Total Voting Rights",
            takeaway="The investment case improved." if model_version != "deterministic-metadata" else "Administrative record.",
            new_information=[],
            reiterated_information=[],
            what_changed={
                "before": "Previous position.",
                "today": "Guidance improves and net debt falls." if model_version != "deterministic-metadata" else "Voting rights updated.",
                "read_through": "Improved position." if model_version != "deterministic-metadata" else "No investment-case change.",
                "coverage_status": "building",
            },
            analyst_view="Good update. Debt falls while earnings expectations improve." if model_version != "deterministic-metadata" else "Routine administrative record.",
            supports_case=[],
            challenges_case=[],
            watch_items=[],
            disclosure_assessment={"status": "partial"},
            source_references=[f"https://example.invalid/{source_id}"],
            source_warnings=[],
            quality_status=quality,
            quality_flags=[],
            confidence=0.9,
            prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
            model_version=model_version,
            analysis_version="aim-intelligence-analyst-3.3",
            is_current=True,
        )
    )


def test_repository_only_feeds_publication_safe_full_analysis_into_editor() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        full_company = CompanyRow(ticker="FULL", company_name="Full Analysis plc")
        routine_company = CompanyRow(ticker="ROUT", company_name="Routine plc")
        review_company = CompanyRow(ticker="REV", company_name="Review plc")
        late_company = CompanyRow(ticker="LATE", company_name="Late plc")
        session.add_all([full_company, routine_company, review_company, late_company])
        session.flush()
        _add_run(session, company=full_company, source_id="full-rns", model_version="recorded")
        _add_run(session, company=routine_company, source_id="routine-rns", model_version="deterministic-metadata")
        _add_run(session, company=review_company, source_id="review-rns", model_version="recorded", quality="review")
        _add_run(session, company=late_company, source_id="late-rns", model_version="recorded", hour=12)

    edition = DailyEditorRepository(factory).get_edition(
        date(2026, 8, 21),
        cutoff=time(12, 0),
    )

    assert edition.candidate_count == 1
    assert edition.lead is not None
    assert edition.lead.primary_source_id == "full-rns"
    assert edition.lead.source_ids == ["full-rns"]

    engine.dispose()
