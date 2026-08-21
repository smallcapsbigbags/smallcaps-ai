from __future__ import annotations

from datetime import date, datetime, timezone

from analyst.models import AnalystNote, AnnouncementInput, DisclosureAssessment, ImpactDriver, KeyFact, QualityReport, WhatChanged
from database.db import create_database_engine, create_session_factory, init_database
from database.product import ProductRepository, _london_bounds
from database.repository import IntelligenceRepository


def repositories():
    engine = create_database_engine("sqlite+pysqlite:///:memory:"); init_database(engine); factory = create_session_factory(engine)
    return IntelligenceRepository(factory), ProductRepository(factory)


def announcement(source_id: str, *, published_at: datetime | None = None, source_url: str = "") -> AnnouncementInput:
    published_at = published_at or datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)
    return AnnouncementInput(source_id=source_id, ticker="ABC", company="ABC plc", published_at=published_at, title="Trading Update", text="Guidance maintained. Net debt reduced to £5m.", source_url=source_url, source_urls=[source_url] if source_url else [], evidence_status="complete", evidence_retrieved_at=published_at, rns_type="Results & trading")


def note(source_id: str, *, facts: list[KeyFact] | None = None, references: list[str] | None = None) -> AnalystNote:
    return AnalystNote(source_id=source_id, rns_type="Results & trading", impact_colour="green", impact_score=3, impact_level="high", impact_rationale="Lower net debt reduces financial risk.", impact_drivers=[ImpactDriver(dimension="balance-sheet", direction="favourable", significance=3, rationale="Net debt reduced.")], headline="Guidance maintained; net debt reduced", takeaway="The balance sheet is the main incremental development.", key_facts=facts or [KeyFact(label="Net debt", value="£5m", basis="reported")], what_changed=WhatChanged(before="Net debt was higher.", today="Net debt is £5m.", read_through="Financial risk reduced."), analyst_view="The balance sheet is the important point.", disclosure_assessment=DisclosureAssessment(status="complete"), source_references=references or [], confidence=0.9)


def save(intelligence: IntelligenceRepository, item: AnnouncementInput, result: AnalystNote, *, quality: str = "publishable") -> None:
    intelligence.save_analysis(item, result, prompt_version="analyst-engine-2.0", model_version="recorded", quality_report=QualityReport(status=quality))


def test_ranked_fact_order_survives_persistence() -> None:
    intelligence, product = repositories(); item = announcement("fact-order")
    save(intelligence, item, note("fact-order", facts=[KeyFact(label="Highest-ranked Z fact", value="£9m", basis="reported"), KeyFact(label="Secondary A fact", value="£1m", basis="reported")]))
    feed = product.list_feed(date(2026, 8, 21))
    assert [fact["label"] for fact in feed[0]["key_facts"]] == ["Highest-ranked Z fact", "Secondary A fact"]
    stored = product.get_note("fact-order"); assert stored is not None
    assert [fact["ordinal"] for fact in stored["key_facts"]] == [0, 1]


def test_event_day_return_is_not_future_one_day_return() -> None:
    intelligence, product = repositories(); item = announcement("price-semantics"); save(intelligence, item, note("price-semantics"))
    stored = product.upsert_price_reaction(source_id="price-semantics", reaction_session="2026-08-21", phase="close", previous_close=100.0, latest_price=105.0, daily_change_pct=5.0, currency="GBp", source="recorded", observed_at=datetime(2026, 8, 21, 16, 35, tzinfo=timezone.utc))
    assert stored["event_day_return"] == 5.0 and stored["daily_change_pct"] == 5.0 and stored["return_1d"] is None


def test_source_links_prefer_verified_announcement_urls_and_reject_unsafe() -> None:
    intelligence, product = repositories(); official = "https://example.com/original-rns"; item = announcement("safe-source", source_url=official)
    save(intelligence, item, note("safe-source", references=["javascript:alert(1)", "https://example.net/corroboration"]))
    assert product.list_feed(date(2026, 8, 21))[0]["source_url"] == official
    stored = product.get_note("safe-source"); assert stored is not None
    assert stored["source_urls"] == [official, "https://example.net/corroboration"]


def test_company_history_count_and_coverage_are_not_truncated() -> None:
    intelligence, product = repositories(); first = announcement("history-1", published_at=datetime(2026, 8, 20, 7, 0, tzinfo=timezone.utc)); second = announcement("history-2")
    save(intelligence, first, note("history-1")); save(intelligence, second, note("history-2"))
    history = product.company_history("ABC", limit=1); assert history is not None
    assert history["announcement_count"] == 2 and history["displayed_count"] == 1 and history["has_more"] is True and history["coverage_since"].startswith("2026-08-20")


def test_review_approval_is_audited_and_enters_public_product() -> None:
    intelligence, product = repositories(); item = announcement("owner-review"); save(intelligence, item, note("owner-review"), quality="review")
    assert product.list_feed(date(2026, 8, 21)) == []
    result = product.approve_review("owner-review", reason="Verified the complete original RNS against the extracted facts.")
    assert result["quality_status"] == "publishable" and product.list_feed(date(2026, 8, 21))[0]["source_id"] == "owner-review"


def test_london_day_bounds_follow_dst_not_fixed_utc_24_hours() -> None:
    spring_start, spring_end = _london_bounds(date(2026, 3, 29)); autumn_start, autumn_end = _london_bounds(date(2026, 10, 25))
    assert (spring_end - spring_start).total_seconds() == 23 * 3600
    assert (autumn_end - autumn_start).total_seconds() == 25 * 3600
