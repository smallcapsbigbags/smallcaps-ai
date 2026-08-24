from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import desc, select

from database.company_sheet import CompanySheetRepository
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow
from product.company_sheet import COMPANY_SHEET_SCHEMA_VERSION, CompanyMetricSeries
from product.monitoring import MONITORING_SCHEMA_VERSION, word_count
from settings import Settings

_NUMERIC_RE = re.compile(r"[-+]?\d")


def _valid_http_url(value: object) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _series_is_publicly_useful(series: CompanyMetricSeries) -> bool:
    if len(series.points) > 1:
        return True
    if not series.points:
        return False
    point = series.points[-1]
    return bool(
        point.value_numeric is not None
        or point.value_low is not None
        or point.value_high is not None
        or _NUMERIC_RE.search(point.value)
    )


def run_company_acceptance(
    database_url: str,
    *,
    allow_sqlite: bool = False,
    require_public_data: bool = False,
) -> dict[str, object]:
    """Verify the publication-safe Company Intelligence read path before deploy."""

    engine = create_database_engine(database_url)
    checks: list[dict[str, object]] = []
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        repository = CompanySheetRepository(factory)

        dialect_ok = allow_sqlite or engine.dialect.name == "postgresql"
        checks.append(
            {
                "code": "COMPANY_SHEET_DATABASE",
                "status": "pass" if dialect_ok else "fail",
                "message": f"Company sheet acceptance is using {engine.dialect.name}.",
            }
        )

        with session_scope(factory) as session:
            anchor = session.execute(
                select(AnnouncementRow, CompanyRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
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
            ).first()

        if anchor is None:
            checks.append(
                {
                    "code": "COMPANY_SHEET_PUBLIC_ANCHOR",
                    "status": "fail" if require_public_data else "pass",
                    "message": "No publishable company record is available.",
                }
            )
        else:
            announcement, company = anchor
            sheet = repository.get_company(company.ticker)
            history_ids = {
                item.source_id for item in list((sheet or {}).history if sheet else [])
            }
            current = sheet.current_position if sheet is not None else None
            current_ok = bool(
                sheet
                and sheet.schema_version == COMPANY_SHEET_SCHEMA_VERSION
                and sheet.ticker == company.ticker
                and sheet.company.strip()
                and current
                and current.schema_version == MONITORING_SCHEMA_VERSION
                and current.source_id == announcement.source_id
                and current.research.verdict.strip()
                and current.what_changed.strip()
                and current.ai_view.strip()
                and word_count(current.ai_view) <= 50
                and _valid_http_url(current.original_source_url)
                and announcement.source_id in history_ids
            )
            checks.append(
                {
                    "code": "COMPANY_SHEET_CURRENT_POSITION",
                    "status": "pass" if current_ok else "fail",
                    "message": (
                        "The latest publishable RNS resolves to its company monitoring sheet."
                        if current_ok
                        else "The latest publishable RNS does not resolve cleanly to Company Intelligence."
                    ),
                    "details": {
                        "ticker": company.ticker,
                        "source_id": announcement.source_id,
                        "history_count": len(history_ids),
                    },
                }
            )

            malformed_history = []
            if sheet is not None:
                malformed_history = [
                    item.source_id
                    for item in sheet.history
                    if not item.headline.strip()
                    or not item.detail_url.startswith("/api/v1/monitoring/")
                    or not _valid_http_url(item.original_source_url)
                ]
            history_ok = bool(sheet and sheet.history and not malformed_history)
            checks.append(
                {
                    "code": "COMPANY_SHEET_RNS_HISTORY",
                    "status": "pass" if history_ok else "fail",
                    "message": (
                        f"Company history exposes {len(sheet.history)} publication-safe RNS record(s)."
                        if history_ok and sheet is not None
                        else "Company history is empty or contains malformed public records."
                    ),
                    "details": {"malformed_source_ids": malformed_history[:20]},
                }
            )

            invalid_metrics = []
            if sheet is not None:
                invalid_metrics = [
                    series.key or series.metric
                    for series in sheet.metrics
                    if not _series_is_publicly_useful(series)
                ]
            metrics_ok = not invalid_metrics
            checks.append(
                {
                    "code": "COMPANY_SHEET_METRIC_DISCIPLINE",
                    "status": "pass" if metrics_ok else "fail",
                    "message": (
                        "Company metrics contain only comparable or genuinely numerical series."
                        if metrics_ok
                        else "Company metrics contain narrative-only one-off facts."
                    ),
                    "details": {"invalid_metric_keys": invalid_metrics[:20]},
                }
            )

            source_urls = []
            if sheet is not None:
                source_urls.extend(item.source_url for item in sheet.guidance if item.source_url)
                source_urls.extend(
                    point.source_url
                    for series in sheet.metrics
                    for point in series.points
                    if point.source_url
                )
                source_urls.extend(
                    item.source_url
                    for item in [
                        *sheet.open_management_claims,
                        *sheet.resolved_management_claims,
                        *sheet.disclosure_gaps,
                    ]
                    if item.source_url
                )
            invalid_sources = [url for url in source_urls if not _valid_http_url(url)]
            provenance_ok = not invalid_sources
            checks.append(
                {
                    "code": "COMPANY_SHEET_SOURCE_PROVENANCE",
                    "status": "pass" if provenance_ok else "fail",
                    "message": (
                        "Company Memory sections retain valid source provenance."
                        if provenance_ok
                        else "Company Memory contains malformed source links."
                    ),
                    "details": {"invalid_source_urls": invalid_sources[:20]},
                }
            )

        failures = [check for check in checks if check["status"] == "fail"]
        return {
            "passed": not failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_dialect": engine.dialect.name,
            "schema_version": COMPANY_SHEET_SCHEMA_VERSION,
            "failure_count": len(failures),
            "checks": checks,
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the SmallcapsBigBags Company Intelligence read model before release."
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

    payload = run_company_acceptance(
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
