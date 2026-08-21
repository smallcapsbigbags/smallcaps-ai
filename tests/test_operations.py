from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock


def test_job_run_lifecycle_is_persisted() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:"); init_database(engine); repository = OperationsRepository(create_session_factory(engine))
    run_id = repository.begin_job("daily-test", run_key="2026-08-21")
    repository.finish_job(run_id, status="degraded", summary={"updated": 3}, warnings=["One item needs review."])
    latest = repository.list_recent(limit=1)[0]
    assert latest["job_name"] == "daily-test" and latest["status"] == "degraded" and latest["summary"]["updated"] == 3 and latest["finished_at"] is not None


def test_local_advisory_lock_rejects_overlap() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    with advisory_job_lock(engine, "same-job") as first:
        assert first is True
        with advisory_job_lock(engine, "same-job") as second:
            assert second is False
