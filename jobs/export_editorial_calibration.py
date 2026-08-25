from __future__ import annotations

import argparse
import json
from pathlib import Path

from database.db import create_database_engine, create_session_factory, init_database
from database.editorial_calibration import EditorialCalibrationRepository
from settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export owner AIM Daily corrections as replayable calibration cases."
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, runtime_warnings = settings.runtime_issues("web")
    if errors:
        raise RuntimeError("; ".join(errors))

    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        cases = EditorialCalibrationRepository(factory).calibration_cases()
        payload = {
            "schema_version": "aim-daily-editor-calibration-v1",
            "case_count": len(cases),
            "cases": cases,
            "runtime_warnings": runtime_warnings,
        }
        text = json.dumps(payload, indent=2, sort_keys=True)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(text, flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
