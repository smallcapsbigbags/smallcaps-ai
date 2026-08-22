from __future__ import annotations

import argparse
import json

from sqlalchemy import Engine

from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock
from database.production_audit import run_production_audit
from settings import Settings

JOB_NAME = "launch-production-audit"
WORKER_JOB_NAMES = ("daily-aim-ingestion", "daily-price-reactions")


def _reconcile_idle_workers(
    engine: Engine,
    operations: OperationsRepository,
) -> tuple[int, list[str]]:
    """Close stale durable rows only when no live process holds the worker lock."""

    reconciled = 0
    active_workers: list[str] = []
    for job_name in WORKER_JOB_NAMES:
        with advisory_job_lock(engine, job_name) as acquired:
            if not acquired:
                active_workers.append(job_name)
                continue
            reconciled += operations.reconcile_stale_running(job_name=job_name)
    return reconciled, active_workers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the live Smallcaps.ai operational record without external calls."
    )
    parser.add_argument(
        "--service",
        choices=["web", "ingestion", "prices"],
        default="web",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Store the audit outcome in job_runs after the inspection.",
    )
    parser.add_argument(
        "--reconcile-stale",
        action="store_true",
        help=(
            "Close worker rows left running for more than three hours, but only "
            "after proving the corresponding advisory lock is idle."
        ),
    )
    parser.add_argument(
        "--allow-sqlite",
        action="store_true",
        help="Permit SQLite for local development; Railway production should omit this.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, runtime_warnings = settings.runtime_issues(args.service)
    if errors:
        payload = {
            "service": args.service,
            "passed": False,
            "runtime_errors": errors,
            "runtime_warnings": runtime_warnings,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        raise SystemExit(1)

    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        operations = OperationsRepository(factory)
        reconciled_stale_jobs = 0
        active_worker_locks: list[str] = []
        if args.reconcile_stale:
            reconciled_stale_jobs, active_worker_locks = _reconcile_idle_workers(
                engine,
                operations,
            )

        report = run_production_audit(
            engine,
            factory,
            service=args.service,
            market_data_enabled=settings.market_data_enabled,
            strict_production=not args.allow_sqlite,
        )
        payload = report.as_dict()
        payload["runtime_warnings"] = runtime_warnings
        payload["reconciled_stale_jobs"] = reconciled_stale_jobs
        payload["active_worker_locks"] = active_worker_locks

        if args.record:
            run_id = operations.begin_job(
                JOB_NAME,
                run_key=f"{args.service}:{report.generated_at.date().isoformat()}",
                summary={"service": args.service},
            )
            warning_messages = [
                f"{check.code}: {check.message}"
                for check in report.checks
                if check.status in {"warning", "fail"}
            ]
            if reconciled_stale_jobs:
                warning_messages.insert(
                    0,
                    f"Reconciled {reconciled_stale_jobs} stale running job record(s).",
                )
            operations.finish_job(
                run_id,
                status=(
                    "failed"
                    if not report.passed
                    else "degraded"
                    if report.warning_count
                    or runtime_warnings
                    or reconciled_stale_jobs
                    else "success"
                ),
                summary={
                    "service": args.service,
                    "passed": report.passed,
                    "warning_count": report.warning_count,
                    "failure_count": report.failure_count,
                    "reconciled_stale_jobs": reconciled_stale_jobs,
                    "active_worker_locks": active_worker_locks,
                    "counts": report.counts,
                    "version_counts": report.version_counts,
                    "warning_codes": [
                        check.code
                        for check in report.checks
                        if check.status == "warning"
                    ],
                    "failure_codes": [
                        check.code
                        for check in report.checks
                        if check.status == "fail"
                    ],
                },
                warnings=[*runtime_warnings, *warning_messages],
                error_text=(
                    "Production readiness audit found launch-blocking failures."
                    if not report.passed
                    else ""
                ),
            )
            payload["recorded_job_run_id"] = run_id

        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        if not report.passed:
            raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
