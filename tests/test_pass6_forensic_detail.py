from __future__ import annotations

from datetime import date
from pathlib import Path

from database.db import create_database_engine, create_session_factory
from database.forensic_monitoring import ForensicMonitoringSheetRepository
from database.monitoring import MonitoringSheetQuery
from jobs.seed_launch_preview import seed as seed_launch_preview
from jobs.seed_pass1_preview import seed as seed_pass1_preview


ROOT = Path(__file__).resolve().parents[1]


def _preview_repository(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pass6-forensic.db'}"
    seed_launch_preview(database_url)
    # Pass 1 appends the deterministic Gamma/Trellus/routine records to the launch set.
    seed_pass1_preview(database_url)
    engine = create_database_engine(database_url)
    repository = ForensicMonitoringSheetRepository(create_session_factory(engine))
    return engine, repository


def test_forensic_projection_uses_stored_takeaway_and_day_reaction(tmp_path) -> None:
    engine, repository = _preview_repository(tmp_path)
    try:
        page = repository.list_rows(
            MonitoringSheetQuery(
                date_from=date(2026, 8, 21),
                date_to=date(2026, 8, 21),
                limit=250,
                sort="latest",
            )
        )
        gamma = next(
            item for item in page.items if item.source_id == "gama-pass1-possible-offer"
        )

        assert gamma.takeaway == (
            "Gamma confirms preliminary discussions with Waterland about a possible "
            "offer for all its shares, while talks with other potential offerors "
            "continue. No offer price or firm intention has been announced."
        )
        assert gamma.takeaway != gamma.ai_view
        assert gamma.market_reaction.previous_close == 969.5
        assert gamma.market_reaction.change_pct == 7.3
        assert gamma.market_reaction.phase == "close"
        assert gamma.market_reaction.currency == "GBp"

        detail = repository.get_detail(gamma.source_id)
        assert detail is not None
        assert detail.takeaway == gamma.takeaway
        assert detail.research.takeaway == gamma.takeaway
        assert detail.research.what_changed.coverage_status == "building"
        assert detail.research.what_changed.today.startswith(
            "Waterland and other parties are in preliminary possible-offer discussions"
        )
        assert [fact.label for fact in detail.research.evidence] == [
            "Offer status",
            "Named possible offeror",
            "Rule 2.6 deadline",
        ]
        assert detail.research.disclosure.missing_items == [
            "Possible offer price and terms."
        ]
    finally:
        engine.dispose()


def test_forensic_detail_keeps_calculation_provenance_and_missing_disclosures(tmp_path) -> None:
    engine, repository = _preview_repository(tmp_path)
    try:
        detail = repository.get_detail("spr-preview-buyback")
        assert detail is not None
        facts = {fact.label: fact for fact in detail.research.evidence}

        assert facts["Maximum buyback"].basis == "reported"
        calculated = facts["Potential share-count reduction"]
        assert calculated.basis == "calculated"
        assert calculated.value == "10.0%"
        assert "11,904,240" in calculated.note
        assert "119,042,400" in calculated.note
        assert detail.research.disclosure.missing_items == [
            "The cash amount committed to the programme."
        ]
        assert detail.research.what_changed.coverage_status == "building"
    finally:
        engine.dispose()


def test_pass6_frontend_is_an_evidence_screen_not_a_second_report() -> None:
    javascript = (ROOT / "frontend" / "assets" / "research.js").read_text(
        encoding="utf-8"
    )
    css = (ROOT / "frontend" / "assets" / "news-detail.css").read_text(
        encoding="utf-8"
    )
    api = (ROOT / "api" / "monitoring.py").read_text(encoding="utf-8")
    acceptance = (ROOT / "jobs" / "monitoring_acceptance.py").read_text(
        encoding="utf-8"
    )

    assert "compactWords(row.takeaway || row.ai_view || row.what_changed, 45)" in javascript
    for label in (
        "EVIDENCE",
        "MATERIAL FACTS",
        "CURRENT BASELINE",
        "WHAT CHANGED",
        "MARKET REACTION",
        "NOT DISCLOSED",
        "SOURCE CHECKS",
        "SOURCE ↗",
    ):
        assert label in javascript

    for retired in (
        'researchBlock("READ-THROUGH"',
        'buildListBlock("WHAT TO WATCH"',
        'buildListBlock("SUPPORTS THE CASE"',
        'buildListBlock("CHALLENGES THE CASE"',
    ):
        assert retired not in javascript

    assert "return_5d" not in javascript
    assert "return_20d" not in javascript
    assert ".forensic-grid" in css
    assert "ForensicMonitoringSheetRepository" in api
    assert "ForensicMonitoringSheetRepository" in acceptance
