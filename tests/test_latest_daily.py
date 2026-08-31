from __future__ import annotations

from datetime import date, datetime, timezone

from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.latest_daily import latest_full_analysis_day
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow


def _add_analysis(
    session,  # type: ignore[no-untyped-def]
    *,
    ticker: str,
    source_id: str,
    published_at: datetime,
    quality_status: str = "publishable",
    model_version: str = "recorded",
    is_current: bool = True,
) -> None:
    company = CompanyRow(ticker=ticker, company_name=f"{ticker} plc")
    session.add(company)
    session.flush()

    announcement = AnnouncementRow(
        company_id=company.id,
        source_id=source_id,
        published_at=published_at,
        headline="Trading Update",
        announcement_type="Results & trading",
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
        source_note="test",
        evidence_status="complete",
        raw_text="Material trading update.",
        categories=[],
    )
    session.add(announcement)
    session.flush()

    session.add(
        AnalystRunRow(
            announcement_id=announcement.id,
            impact_colour="green",
            impact_score=4,
            impact_level="high",
            impact_rationale="Decision-useful change.",
            impact_drivers=[],
            headline="Trading improves",
            takeaway="The disclosed position improved.",
            new_information=[],
            reiterated_information=[],
            what_changed={
                "before": "Previous position.",
                "today": "Improved position.",
                "read_through": "Improved position.",
                "coverage_status": "complete",
            },
            analyst_view="Material improvement.",
            supports_case=[],
            challenges_case=[],
            watch_items=[],
            disclosure_assessment={"status": "complete"},
            source_references=[f"https://example.invalid/{source_id}"],
            source_warnings=[],
            quality_status=quality_status,
            quality_flags=[],
            confidence=0.95,
            prompt_version="analyst-engine-3.4-facts-no-fluff-routing",
            model_version=model_version,
            analysis_version="aim-intelligence-analyst-3.4",
            is_current=is_current,
        )
    )


def test_latest_daily_date_respects_selected_edition_cutoff() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        # 07:30 Europe/London: eligible for the 08:00 morning edition.
        _add_analysis(
            session,
            ticker="MORN",
            source_id="morning-eligible",
            published_at=datetime(2026, 8, 25, 6, 30, tzinfo=timezone.utc),
        )
        # 09:00 Europe/London: only eligible for the close edition.
        _add_analysis(
            session,
            ticker="LATE",
            source_id="close-only",
            published_at=datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc),
        )
        # Newer rows that are not publication-safe FULL analyses must be ignored.
        _add_analysis(
            session,
            ticker="REV",
            source_id="owner-review",
            published_at=datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc),
            quality_status="review",
        )
        _add_analysis(
            session,
            ticker="META",
            source_id="routine-metadata",
            published_at=datetime(2026, 8, 30, 6, 0, tzinfo=timezone.utc),
            model_version="deterministic-metadata-v1",
        )

    assert latest_full_analysis_day(
        factory,
        on_or_before=date(2026, 8, 31),
        edition_state="morning_note",
    ) == date(2026, 8, 25)
    assert latest_full_analysis_day(
        factory,
        on_or_before=date(2026, 8, 31),
        edition_state="aim_close",
    ) == date(2026, 8, 28)

    engine.dispose()


def test_latest_daily_date_returns_none_without_safe_full_analysis() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        _add_analysis(
            session,
            ticker="REV",
            source_id="review-only",
            published_at=datetime(2026, 8, 25, 6, 30, tzinfo=timezone.utc),
            quality_status="review",
        )

    assert latest_full_analysis_day(
        factory,
        on_or_before=date(2026, 8, 31),
        edition_state="morning_note",
    ) is None

    engine.dispose()
