from __future__ import annotations

from datetime import date, datetime, timezone

from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow, FactRow
from database.newsroom import NewsroomRepository


def _run(session, *, announcement: AnnouncementRow, impact: int, headline: str, view: str) -> AnalystRunRow:
    run = AnalystRunRow(
        announcement_id=announcement.id,
        impact_colour="green",
        impact_score=impact,
        impact_level="high" if impact >= 3 else "medium",
        impact_rationale="Decision-useful change.",
        impact_drivers=[],
        headline=headline,
        takeaway="Balance sheet improved.",
        new_information=[],
        reiterated_information=[],
        what_changed={
            "before": "Net debt was higher.",
            "today": "Net debt fell to £18.2m from £24.0m.",
            "read_through": "Financial risk is lower.",
            "coverage_status": "building",
        },
        analyst_view=view,
        supports_case=[],
        challenges_case=[],
        watch_items=["Check cash conversion at the full-year results."],
        disclosure_assessment={"status": "partial", "missing_items": []},
        source_references=[announcement.source_url],
        source_warnings=[],
        quality_status="publishable",
        quality_flags=[],
        confidence=0.9,
        prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
        model_version="recorded",
        analysis_version="aim-intelligence-analyst-3.3",
        is_current=True,
    )
    session.add(run)
    session.flush()
    return run


def test_newsroom_repository_adds_prior_comparable_metric_context() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        company = CompanyRow(ticker="SPR", company_name="Springfield Properties plc")
        session.add(company)
        session.flush()

        prior = AnnouncementRow(
            company_id=company.id,
            source_id="spr-prior",
            published_at=datetime(2026, 5, 12, 6, 0, tzinfo=timezone.utc),
            headline="Trading Update",
            announcement_type="Results & trading",
            source_url="https://example.com/spr-prior",
            source_urls=["https://example.com/spr-prior"],
            source_note="test",
            evidence_status="complete",
            raw_text="Net debt was £24.0m.",
            categories=[],
        )
        session.add(prior)
        session.flush()
        prior_run = _run(session, announcement=prior, impact=2, headline="Debt falls", view="Useful progress.")
        session.add(
            FactRow(
                company_id=company.id,
                announcement_id=prior.id,
                analyst_run_id=prior_run.id,
                ordinal=0,
                label="Net debt",
                metric="Net debt",
                period="",
                value="£24.0m",
                unit="m",
                currency="GBP",
                as_of_date="2026-05-12",
                value_numeric=24.0,
                basis="reported",
                note="",
                comparator="",
                comparator_type="none",
                comparator_source_id="",
                previous_value="",
                information_status="new",
            )
        )

        current = AnnouncementRow(
            company_id=company.id,
            source_id="spr-current",
            published_at=datetime(2026, 8, 25, 6, 10, tzinfo=timezone.utc),
            headline="Trading Update",
            announcement_type="Results & trading",
            source_url="https://example.com/spr-current",
            source_urls=["https://example.com/spr-current"],
            source_note="test",
            evidence_status="complete",
            raw_text="Net debt fell to £18.2m from £24.0m.",
            categories=[],
        )
        session.add(current)
        session.flush()
        current_run = _run(
            session,
            announcement=current,
            impact=4,
            headline="Springfield cuts net debt again",
            view="Good balance-sheet progress while earnings expectations remain intact.",
        )
        session.add(
            FactRow(
                company_id=company.id,
                announcement_id=current.id,
                analyst_run_id=current_run.id,
                ordinal=0,
                label="Net debt",
                metric="Net debt",
                period="",
                value="£18.2m",
                unit="m",
                currency="GBP",
                as_of_date="2026-08-25",
                value_numeric=18.2,
                basis="reported",
                note="",
                comparator="Prior comparable disclosure",
                comparator_type="prior-disclosure",
                comparator_source_id="spr-prior",
                previous_value="£24.0m",
                information_status="new",
            )
        )

    edition = NewsroomRepository(factory).get_edition(date(2026, 8, 25), edition_state="morning_note")
    articles = [*edition.also_matters, *edition.quick_takes]

    assert edition.published_article_count == 1
    assert edition.withheld_story_count == 0
    assert len(articles) == 1
    article = articles[0]
    assert article.copydesk_status == "pass"
    assert article.the_number is not None
    assert [point.value for point in article.the_number.points] == ["£24.0m", "£18.2m"]
    assert article.context
    assert article.news.provenance
    assert article.news.provenance[0].source_id == "spr-current"

    engine.dispose()
