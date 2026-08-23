from __future__ import annotations

from datetime import date

from database.db import create_database_engine, create_session_factory
from database.product import ProductRepository
from jobs.seed_launch_preview import seed as seed_launch_preview
from jobs.seed_pass1_preview import seed as seed_pass1_preview


def test_pass1_preview_covers_critical_mixed_favourable_and_routine_states(
    tmp_path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pass1-preview.db'}"
    seed_launch_preview(database_url)
    seed_pass1_preview(database_url)

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    feed = ProductRepository(factory).list_feed(date(2026, 8, 21))

    by_ticker = {item["ticker"]: item for item in feed}
    assert by_ticker["TRLS"]["impact_score"] == 5
    assert by_ticker["TRLS"]["impact_colour"] == "red"
    assert by_ticker["TRLS"]["rns_type"] == "Other"
    assert by_ticker["TRLS"]["analyst_view"].startswith("Thesis broken.")
    assert by_ticker["GAMA"]["impact_score"] == 4
    assert by_ticker["GAMA"]["impact_colour"] == "amber"
    assert "not yet a bid" in by_ticker["GAMA"]["analyst_view"]
    assert by_ticker["SPR"]["impact_colour"] == "green"
    assert by_ticker["ROUT"]["impact_score"] == 1
    assert by_ticker["ROUT"]["impact_colour"] == "grey"
    assert feed[0]["ticker"] == "TRLS"

    engine.dispose()
