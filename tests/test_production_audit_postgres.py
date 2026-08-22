from __future__ import annotations

import os

import pytest
from sqlalchemy import func, select

from database.db import create_database_engine, create_session_factory, init_database
from database.models import Base, JobRunRow
from database.production_audit import _write_probe


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"),
    reason="TEST_POSTGRES_URL is not configured",
)
def test_production_write_probe_round_trips_and_rolls_back_on_postgres() -> None:
    engine = create_database_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.drop_all(engine)
    init_database(engine)

    writable, error = _write_probe(engine)

    assert engine.dialect.name == "postgresql"
    assert writable is True
    assert error == ""

    factory = create_session_factory(engine)
    with factory() as session:
        probe_rows = session.scalar(
            select(func.count())
            .select_from(JobRunRow)
            .where(JobRunRow.job_name == "production-audit-write-probe")
        )
    assert probe_rows == 0

    Base.metadata.drop_all(engine)
    engine.dispose()
