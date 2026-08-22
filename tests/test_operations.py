import uuid
from datetime import datetime, timedelta, timezone

from database.db import create_database_engine, create_session_factory, init_database
from database.models import JobRunRow
from database.operations import OperationsRepository, advisory_job_lock


def test_job_run_lifecycle_is_persisted() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    repository = OperationsRepository(create_session_factory(engine))
    run_id = repository.begin_job("daily-test", run_key="2026-08-21")
    repository.finish_job(
        run_id,
        status="degraded",
        summary={"updated": 3},
        warnings=["One item needs review."],
    )
    latest = repository.list_recent(limit=1)[0]
    assert latest["job_name"] == "daily-test"
    assert latest["status"] == "degraded"
    assert latest["summary"]["updated"] == 3
    assert latest["finished_at"] is not None


def test_local_advisory_lock_rejects_overlap() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    with advisory_job_lock(engine, "same-job") as first:
        assert first is True
        with advisory_job_lock(engine, "same-job") as second:
            assert second is False


def test_stale_running_job_is_reconciled_without_touching_recent_run() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    repository = OperationsRepository(create_session_factory(engine))
    now = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)

    stale_id = repository.begin_job("daily-aim-ingestion", run_key="stale")
    recent_id = repository.begin_job("daily-aim-ingestion", run_key="recent")

    with repository.session_factory() as session:
        stale = session.get(JobRunRow, uuid.UUID(stale_id))
        recent = session.get(JobRunRow, uuid.UUID(recent_id))
        assert stale is not None and recent is not None
        stale.started_at = now - timedelta(hours=4)
        recent.started_at = now - timedelta(minutes=20)
        session.commit()

    reconciled = repository.reconcile_stale_running(
        job_name="daily-aim-ingestion",
        max_age=timedelta(hours=3),
        now=now,
    )

    assert reconciled == 1
    rows = {item["run_key"]: item for item in repository.list_recent(limit=5)}
    assert rows["stale"]["status"] == "failed"
    assert rows["stale"]["finished_at"] is not None
    assert "terminated" in rows["stale"]["error_text"].lower()
    assert rows["recent"]["status"] == "running"
    assert rows["recent"]["finished_at"] is None
