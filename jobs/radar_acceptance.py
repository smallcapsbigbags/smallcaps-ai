from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, select

from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.radar import RadarCompanyStateRow, RadarSetupRow
from jobs.run_radar_benchmark import run_benchmark
from product.radar import RADAR_SCHEMA_VERSION, RADAR_VERSION
from settings import Settings


def run_radar_acceptance(
    database_url: str,
    *,
    allow_sqlite: bool = False,
    benchmark_path: str = "benchmarks/radar_cases.json",
) -> dict[str, object]:
    engine = create_database_engine(database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        dialect_ok = allow_sqlite or engine.dialect.name == "postgresql"
        tables = set(inspect(engine).get_table_names())
        required_tables = {"radar_company_states", "radar_setups"}
        missing_tables = sorted(required_tables - tables)
        benchmark = run_benchmark(Path(benchmark_path))

        with session_scope(factory) as session:
            active_count = len(
                session.execute(
                    select(RadarSetupRow.id).where(
                        RadarSetupRow.status.in_(["new", "active"])
                    )
                ).all()
            )
            state_count = len(session.execute(select(RadarCompanyStateRow.id)).all())

        checks: list[dict[str, object]] = [
            {
                "code": "RADAR_DATABASE",
                "status": "pass" if dialect_ok else "fail",
                "message": (
                    f"AIM Radar acceptance is using {engine.dialect.name}."
                    if dialect_ok
                    else "Production AIM Radar acceptance must use PostgreSQL."
                ),
            },
            {
                "code": "RADAR_SCHEMA",
                "status": "pass" if not missing_tables else "fail",
                "message": (
                    "Radar persistence tables are present."
                    if not missing_tables
                    else f"Radar persistence tables are missing: {missing_tables}."
                ),
                "details": {
                    "required_tables": sorted(required_tables),
                    "missing_tables": missing_tables,
                    "active_setup_count": active_count,
                    "company_state_count": state_count,
                },
            },
            {
                "code": "RADAR_BENCHMARK",
                "status": "pass" if benchmark["passed"] else "fail",
                "message": (
                    f"Radar benchmark passed {benchmark['passed_cases']}/{benchmark['case_count']} cases."
                    if benchmark["passed"]
                    else f"Radar benchmark failed: {benchmark['failed_cases']}."
                ),
                "details": {
                    "case_count": benchmark["case_count"],
                    "passed_cases": benchmark["passed_cases"],
                    "failed_cases": benchmark["failed_cases"],
                },
            },
        ]
        failures = [item for item in checks if item["status"] == "fail"]
        return {
            "passed": not failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_dialect": engine.dialect.name,
            "schema_version": RADAR_SCHEMA_VERSION,
            "radar_version": RADAR_VERSION,
            "failure_count": len(failures),
            "checks": checks,
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the AIM Radar foundation.")
    parser.add_argument("--allow-sqlite", action="store_true")
    parser.add_argument("--benchmark", default="benchmarks/radar_cases.json")
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, runtime_warnings = settings.runtime_issues("web")
    if errors:
        payload: dict[str, object] = {
            "passed": False,
            "runtime_errors": errors,
            "runtime_warnings": runtime_warnings,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        raise SystemExit(1)

    payload = run_radar_acceptance(
        settings.database_url,
        allow_sqlite=args.allow_sqlite,
        benchmark_path=args.benchmark,
    )
    payload["runtime_warnings"] = runtime_warnings
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
