from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select

from database.daily_editor import DailyEditorRepository
from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.models import AnalystRunRow, AnnouncementRow
from settings import Settings

LONDON = ZoneInfo("Europe/London")


def _valid_http_url(value: object) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _latest_full_public_day(factory):
    with session_scope(factory) as session:
        row = session.execute(
            select(AnnouncementRow.published_at, AnnouncementRow.source_id)
            .join(
                AnalystRunRow,
                AnalystRunRow.announcement_id == AnnouncementRow.id,
            )
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
                ~AnalystRunRow.model_version.like("deterministic-metadata%"),
            )
            .order_by(desc(AnnouncementRow.published_at))
            .limit(1)
        ).first()
    if row is None:
        return None
    published_at, source_id = row
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at.astimezone(LONDON).date(), str(source_id)


def run_daily_editor_acceptance(
    database_url: str,
    *,
    allow_sqlite: bool = False,
    require_public_data: bool = False,
) -> dict[str, object]:
    engine = create_database_engine(database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        dialect_ok = allow_sqlite or engine.dialect.name == "postgresql"
        anchor = _latest_full_public_day(factory)

        checks: list[dict[str, object]] = [
            {
                "code": "AIM_DAILY_DATABASE",
                "status": "pass" if dialect_ok else "fail",
                "message": (
                    f"AIM Daily acceptance is using {engine.dialect.name}."
                    if dialect_ok
                    else "Production AIM Daily acceptance must use PostgreSQL."
                ),
            }
        ]

        if anchor is None:
            checks.append(
                {
                    "code": "AIM_DAILY_PUBLIC_DATA",
                    "status": "fail" if require_public_data else "pass",
                    "message": (
                        "No publication-safe FULL analysis exists for AIM Daily."
                        if require_public_data
                        else "No publication-safe FULL analysis exists; data was optional."
                    ),
                }
            )
        else:
            day, anchor_source_id = anchor
            edition = DailyEditorRepository(factory).get_edition(
                day,
                cutoff=time(23, 59),
            )
            surfaced = [
                *([edition.lead] if edition.lead is not None else []),
                *edition.also_matters,
                *edition.quick_takes,
            ]
            malformed = [
                story.primary_source_id
                for story in surfaced
                if not story.editorial_headline.strip()
                or not story.why_it_matters.strip()
                or not story.source_urls
                or not all(_valid_http_url(url) for url in story.source_urls)
            ]
            count_ok = (
                edition.candidate_count >= 1
                and edition.other_analysed_count <= edition.candidate_count
                and edition.published_story_count == len(surfaced)
            )
            contract_ok = (
                edition.schema_version == "aim-daily-editor-v1"
                and edition.editor_version == "aim-daily-editor-1.0"
                and count_ok
                and not malformed
            )
            checks.append(
                {
                    "code": "AIM_DAILY_EDITOR_READ_MODEL",
                    "status": "pass" if contract_ok else "fail",
                    "message": (
                        f"AIM Daily editor produced {edition.published_story_count} story/stories from {edition.candidate_count} publication-safe FULL candidate(s)."
                        if contract_ok
                        else "AIM Daily editor contract is malformed or its counts are inconsistent."
                    ),
                    "details": {
                        "date": day.isoformat(),
                        "anchor_source_id": anchor_source_id,
                        "candidate_count": edition.candidate_count,
                        "published_story_count": edition.published_story_count,
                        "other_analysed_count": edition.other_analysed_count,
                        "quiet_morning": edition.quiet_morning,
                        "malformed_source_ids": malformed,
                    },
                }
            )

        failures = [item for item in checks if item["status"] == "fail"]
        return {
            "passed": not failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_dialect": engine.dialect.name,
            "schema_version": "aim-daily-editor-v1",
            "editor_version": "aim-daily-editor-1.0",
            "failure_count": len(failures),
            "checks": checks,
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the publication-safe AIM Daily editor read model."
    )
    parser.add_argument("--allow-sqlite", action="store_true")
    parser.add_argument("--require-public-data", action="store_true")
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

    payload = run_daily_editor_acceptance(
        settings.database_url,
        allow_sqlite=args.allow_sqlite,
        require_public_data=args.require_public_data,
    )
    payload["runtime_warnings"] = runtime_warnings
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
