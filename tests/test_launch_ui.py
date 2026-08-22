from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from database.feed_navigation import latest_publishable_day
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    CorrectionRow,
)
from database.publication_safety import reconcile_publication_safety
from ui.common import APP_CSS, impact_badge, price_markup, safe_http_url


def _add_analysis(
    factory,
    *,
    source_id: str,
    published_at: datetime,
    quality_status: str = "publishable",
    source_url: str = "https://example.com/rns",
    evidence_status: str = "complete",
    raw_text: str = (
        "This is a full regulatory announcement containing enough evidence for "
        "a public Smallcaps.ai analysis record."
    ),
) -> None:
    with session_scope(factory) as session:
        company = session.scalar(
            select(CompanyRow).where(CompanyRow.ticker == "SPR")
        )
        if company is None:
            company = CompanyRow(
                ticker="SPR",
                company_name="Springfield Properties plc",
            )
            session.add(company)
            session.flush()
        announcement = AnnouncementRow(
            company_id=company.id,
            source_id=source_id,
            published_at=published_at,
            headline="Trading Update",
            announcement_type="Results & trading",
            source_url=source_url,
            source_urls=[source_url] if source_url else [],
            source_note="",
            evidence_status=evidence_status,
            evidence_retrieved_at=published_at,
            raw_text=raw_text,
            categories=["Trading update"],
        )
        session.add(announcement)
        session.flush()
        session.add(
            AnalystRunRow(
                announcement_id=announcement.id,
                impact_colour="green",
                impact_score=3,
                impact_level="high",
                impact_rationale="Balance-sheet risk reduced.",
                impact_drivers=[],
                headline="Net debt falls",
                takeaway="The company reported lower net debt.",
                new_information=["Net debt fell."],
                reiterated_information=[],
                what_changed={
                    "before": "Debt was higher.",
                    "today": "Debt is lower.",
                    "read_through": "Financial risk reduced.",
                    "coverage_status": "building",
                },
                analyst_view="The balance sheet improved.",
                supports_case=["Lower debt."],
                challenges_case=[],
                watch_items=["Next debt update."],
                disclosure_assessment={"status": "complete"},
                source_references=[source_url] if source_url else [],
                source_warnings=[],
                quality_status=quality_status,
                quality_flags=[],
                confidence=0.9,
                prompt_version="analyst-engine-3.1-sector-intelligence",
                model_version="launch-test",
                analysis_version="aim-intelligence-analyst-3.1",
                is_current=True,
            )
        )


def test_latest_feed_day_ignores_review_records() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    _add_analysis(
        factory,
        source_id="published-friday",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
    )
    _add_analysis(
        factory,
        source_id="review-saturday",
        published_at=datetime(2026, 8, 22, 7, 0, tzinfo=timezone.utc),
        quality_status="review",
    )

    assert latest_publishable_day(factory).isoformat() == "2026-08-21"


def test_publication_safety_moves_unsafe_record_to_review_with_audit() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    _add_analysis(
        factory,
        source_id="unsafe-row",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        source_url="",
        raw_text="Too short",
    )

    result = reconcile_publication_safety(factory, corrected_by="test")

    assert result.inspected == 1
    assert result.moved_to_review == 1
    assert result.source_ids == ("unsafe-row",)
    with session_scope(factory) as session:
        run = session.scalar(select(AnalystRunRow))
        correction_count = session.scalar(
            select(func.count()).select_from(CorrectionRow)
        )
        assert run is not None
        assert run.quality_status == "review"
        assert any(
            flag.get("code") == "PUBLICATION_SAFETY_REVIEW"
            for flag in run.quality_flags
        )
        assert correction_count == 1


def test_publication_safety_leaves_valid_record_public() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    _add_analysis(
        factory,
        source_id="safe-row",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
    )

    result = reconcile_publication_safety(factory)

    assert result.inspected == 1
    assert result.moved_to_review == 0
    with session_scope(factory) as session:
        run = session.scalar(select(AnalystRunRow))
        assert run is not None
        assert run.quality_status == "publishable"


def test_customer_ui_exposes_direction_and_rejects_unsafe_links() -> None:
    badge = impact_badge("green", "high")
    assert "IMPACT HIGH · GREEN" in badge
    assert safe_http_url("https://example.com/rns") == "https://example.com/rns"
    assert safe_http_url("javascript:alert(1)") == ""
    assert safe_http_url("not-a-url") == ""
    assert price_markup(None) == ""
    assert price_markup({"daily_change_pct": None}) == ""


def test_mobile_and_beta_launch_styles_are_present() -> None:
    assert "sca-table-responsive" in APP_CSS
    assert "data-label" in APP_CSS
    assert "sca-beta-points" in APP_CSS
    assert "sca-footer" in APP_CSS
