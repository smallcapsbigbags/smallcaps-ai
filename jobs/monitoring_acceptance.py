from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select

from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from database.models import AnalystRunRow, AnnouncementRow
from database.monitoring import MonitoringSheetQuery, MonitoringSheetRepository
from product.monitoring import MONITORING_SCHEMA_VERSION, word_count
from settings import Settings

LONDON = ZoneInfo("Europe/London")


def _valid_http_url(value: object) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def run_monitoring_acceptance(
    database_url: str,
    *,
    allow_sqlite: bool = False,
    require_public_data: bool = False,
) -> dict[str, object]:
    engine = create_database_engine(database_url)
    checks: list[dict[str, object]] = []
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        repository = MonitoringSheetRepository(factory)
        dialect_ok = allow_sqlite or engine.dialect.name == "postgresql"
        checks.append(
            {
                "code": "MONITORING_DATABASE",
                "status": "pass" if dialect_ok else "fail",
                "message": f"Monitoring acceptance is using {engine.dialect.name}.",
            }
        )

        with session_scope(factory) as session:
            anchor = session.execute(
                select(AnnouncementRow)
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                )
                .order_by(desc(AnnouncementRow.published_at))
                .limit(1)
            ).scalar_one_or_none()

        if anchor is None:
            checks.append(
                {
                    "code": "MONITORING_PUBLIC_ANCHOR",
                    "status": "fail" if require_public_data else "pass",
                    "message": "No publishable monitoring record is available.",
                }
            )
        else:
            published = anchor.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            day = published.astimezone(LONDON).date()
            page = repository.list_rows(
                MonitoringSheetQuery(
                    date_from=day,
                    date_to=day,
                    limit=250,
                    sort="latest",
                )
            )
            anchor_row = next(
                (item for item in page.items if item.source_id == anchor.source_id),
                None,
            )
            malformed = [
                item.source_id
                for item in page.items
                if not item.ticker.strip()
                or not item.company.strip()
                or not item.rns_title.strip()
                or not item.rns_type.strip()
                or not item.what_changed.strip()
                or not item.ai_view.strip()
                or word_count(item.ai_view) > 50
                or not _valid_http_url(item.original_source_url)
                or not item.detail_url.startswith("/api/v1/monitoring/")
            ]
            row_ok = (
                page.schema_version == MONITORING_SCHEMA_VERSION
                and anchor_row is not None
                and not malformed
            )
            checks.append(
                {
                    "code": "MONITORING_SHEET_READ_MODEL",
                    "status": "pass" if row_ok else "fail",
                    "message": (
                        f"Monitoring read model returned {page.count} valid public row(s)."
                        if row_ok
                        else "Monitoring read model is missing the latest row or contains malformed output."
                    ),
                    "details": {
                        "anchor_source_id": anchor.source_id,
                        "malformed_source_ids": malformed[:20],
                    },
                }
            )

            detail = repository.get_detail(anchor.source_id)
            detail_ok = bool(
                detail
                and detail.source_id == anchor.source_id
                and detail.research.verdict.strip()
                and detail.research.what_changed.today == detail.what_changed
                and any(
                    _valid_http_url(url)
                    for url in detail.research.provenance.source_urls
                )
            )
            checks.append(
                {
                    "code": "MONITORING_DETAIL_READ_MODEL",
                    "status": "pass" if detail_ok else "fail",
                    "message": (
                        "The latest monitoring row resolves to complete expanded research."
                        if detail_ok
                        else "The latest monitoring row does not resolve to complete expanded research."
                    ),
                    "details": {"source_id": anchor.source_id},
                }
            )

            health = repository.health()
            health_ok = (
                health.get("status") == "ok"
                and health.get("schema_version") == MONITORING_SCHEMA_VERSION
            )
            checks.append(
                {
                    "code": "MONITORING_API_HEALTH_MODEL",
                    "status": "pass" if health_ok else "fail",
                    "message": (
                        "Monitoring health model is ready."
                        if health_ok
                        else "Monitoring health model failed."
                    ),
                    "details": health,
                }
            )

        failures = [check for check in checks if check["status"] == "fail"]
        return {
            "passed": not failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_dialect": engine.dialect.name,
            "schema_version": MONITORING_SCHEMA_VERSION,
            "failure_count": len(failures),
            "checks": checks,
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the SmallcapsBigBags monitoring read model before release."
    )
    parser.add_argument("--allow-sqlite", action="store_true")
    parser.add_argument("--require-public-data", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("web")
    if errors:
        print(
            json.dumps(
                {
                    "passed": False,
                    "runtime_errors": errors,
                    "runtime_warnings": warnings,
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
        raise SystemExit(1)

    payload = run_monitoring_acceptance(
        settings.database_url,
        allow_sqlite=args.allow_sqlite,
        require_public_data=args.require_public_data,
    )
    payload["runtime_warnings"] = warnings
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
