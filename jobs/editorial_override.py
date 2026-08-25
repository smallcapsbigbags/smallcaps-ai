from __future__ import annotations

import argparse
import json
from datetime import date

from database.daily_editor import DailyEditorRepository
from database.db import create_database_engine, create_session_factory, init_database
from database.editorial_calibration import EditorialCalibrationRepository
from settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record an audited owner override for the AIM Daily editor."
    )
    parser.add_argument("--date", required=True, help="Edition date, YYYY-MM-DD")
    parser.add_argument(
        "--state",
        required=True,
        choices=["early_read", "morning_note", "aim_close"],
        help="Edition state used to capture the algorithmic baseline.",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["lead", "promote", "demote", "suppress", "group"],
    )
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--target-source-id", default="")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--created-by", default="owner")
    args = parser.parse_args()

    day = date.fromisoformat(args.date)
    settings = Settings.from_env()
    errors, runtime_warnings = settings.runtime_issues("web")
    if errors:
        raise RuntimeError("; ".join(errors))

    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        calibration = EditorialCalibrationRepository(factory)
        calibration.ensure_story_links(day)
        editor = DailyEditorRepository(factory)
        snapshot = editor.algorithm_snapshot(
            day,
            source_id=args.source_id,
            edition_state=args.state,
        )
        result = calibration.record_override(
            day=day,
            edition_state=args.state,
            action=args.action,
            source_id=args.source_id,
            target_source_id=args.target_source_id,
            reason=args.reason,
            algorithm_score=int(snapshot["algorithm_score"]),
            algorithm_bucket=str(snapshot["algorithm_bucket"]),  # type: ignore[arg-type]
            algorithm_story_key=str(snapshot["story_key"]),
            snapshot=snapshot,
            created_by=args.created_by,
        )
        payload = {
            "recorded": True,
            "override": result,
            "runtime_warnings": runtime_warnings,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
