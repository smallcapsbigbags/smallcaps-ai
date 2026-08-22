from __future__ import annotations

import argparse
import json

from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository
from database.production_audit import run_production_audit
from settings import Settings

JOB_NAME = "launch-production-audit"


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
        help="Close worker rows left running for more than three hours before auditing.",
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
        reconciled_stale_jobs = (
            operations.reconcile_stale_running()
            if args.reconcile_stale
            else 0
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
