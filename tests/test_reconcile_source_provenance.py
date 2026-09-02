from __future__ import annotations

from datetime import datetime, timezone

from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from database.models import AnnouncementRow, CompanyRow
from jobs.reconcile_source_provenance import reconcile_source_provenance


def test_reconciliation_reorders_existing_sources_without_schema_change() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    mirror = "https://www.lse.co.uk/rns/ABC/example.html"
    fca = "https://data.fca.org.uk/artefacts/NSM/RNS/example.html"
    with session_scope(factory) as session:
        company = CompanyRow(ticker="ABC", company_name="Example plc")
        session.add(company)
        session.flush()
        session.add(
            AnnouncementRow(
                company_id=company.id,
                source_id="aim-test",
                published_at=datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc),
                headline="Trading Update",
                source_url=mirror,
                source_urls=[mirror, fca],
                raw_text="Example",
            )
        )

    dry_run = reconcile_source_provenance(factory, apply=False)
    assert dry_run.scanned == 1
    assert dry_run.reordered == 1
    assert dry_run.fca_nsm == 1

    with session_scope(factory) as session:
        row = session.query(AnnouncementRow).one()
        assert row.source_url == mirror

    applied = reconcile_source_provenance(factory, apply=True)
    assert applied.reordered == 1

    with session_scope(factory) as session:
        row = session.query(AnnouncementRow).one()
        assert row.source_url == fca
        assert row.source_urls == [fca, mirror]

    final = reconcile_source_provenance(factory, apply=False)
    assert final.reordered == 0
    engine.dispose()
