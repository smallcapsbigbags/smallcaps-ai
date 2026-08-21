from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import inspect, text

from database.db import create_database_engine, init_database
from settings import Settings

REQUIRED_TABLES = {"companies", "announcements", "analyst_runs", "facts", "guidance_events", "management_claims", "price_reactions", "corrections", "job_runs"}


def validate(service: str, *, create_schema: bool) -> dict[str, Any]:
    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues(service)
    result: dict[str, Any] = {"service": service, "railway": settings.running_on_railway, "database": "postgresql" if settings.uses_postgres else "sqlite", "private_beta_mode": settings.private_beta_mode, "errors": list(errors), "warnings": list(warnings)}
    if errors:
        return result
    engine = create_database_engine(settings.database_url)
    try:
        if create_schema:
            init_database(engine)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        tables = set(inspect(engine).get_table_names())
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            result["errors"].append("Missing database tables: " + ", ".join(missing))
        result["table_count"] = len(tables)
        result["schema_ready"] = not missing
    except Exception as exc:
        result["errors"].append(f"Database validation failed: {type(exc).__name__}: {exc}")
    finally:
        engine.dispose()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Smallcaps.ai Railway runtime configuration.")
    parser.add_argument("--service", choices=["web", "ingestion", "prices", "benchmark"], default="web")
    parser.add_argument("--create-schema", action="store_true")
    args = parser.parse_args()
    result = validate(args.service, create_schema=args.create_schema)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
