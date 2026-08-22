from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from database.company_intelligence import CompanyIntelligenceRepository
from database.db import create_database_engine, create_session_factory
from settings import Settings


def _parse_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic integrity checks over a Company Intelligence snapshot."""

    errors: list[str] = []
    warnings: list[str] = []
    announcement_count = int(snapshot.get("announcement_count") or 0)
    coverage_days = int(snapshot.get("coverage_days") or 0)
    status = str(snapshot.get("coverage_status") or "building")
    expected_status = (
        "established"
        if announcement_count >= 6 and coverage_days >= 365
        else "building"
    )
    if status != expected_status:
        errors.append(
            f"coverage_status={status!r}, expected {expected_status!r} from "
            f"announcement_count={announcement_count}, coverage_days={coverage_days}"
        )

    generated_before = _parse_datetime(snapshot.get("generated_before"))
    source_ids: set[str] = set()
    calculated_series = 0
    comparable_series = 0

    for series in snapshot.get("metric_series") or []:
        key = str(series.get("key") or "").strip()
        metric = str(series.get("metric") or "").strip()
        basis = str(series.get("basis") or "").strip()
        points = list(series.get("points") or [])
        if not key or not metric or not points:
            errors.append("metric series is missing key, metric or points")
            continue
        if basis == "calculated":
            calculated_series += 1
        if len(points) > 1:
            comparable_series += 1
        point_dates: list[datetime] = []
        for point in points:
            source_id = str(point.get("source_id") or "").strip()
            if not source_id:
                errors.append(f"metric series {key!r} has a point without source_id")
            else:
                source_ids.add(source_id)
            if str(point.get("basis") or "") != basis:
                errors.append(
                    f"metric series {key!r} mixes basis {basis!r} with "
                    f"{point.get('basis')!r}"
                )
            published_at = _parse_datetime(point.get("published_at"))
            if published_at is None:
                errors.append(
                    f"metric series {key!r} has an invalid published_at value"
                )
                continue
            point_dates.append(published_at)
            if generated_before is not None and published_at >= generated_before:
                errors.append(
                    f"metric series {key!r} contains source {source_id!r} at or "
                    "after generated_before"
                )
        if point_dates != sorted(point_dates):
            errors.append(f"metric series {key!r} is not chronological")
        if points and str(series.get("latest_value") or "") != str(
            points[-1].get("value") or ""
        ):
            errors.append(f"metric series {key!r} latest_value does not match last point")

    guidance_keys: set[str] = set()
    for item in snapshot.get("current_guidance") or []:
        key = str(item.get("key") or "").strip()
        source_id = str(item.get("source_id") or "").strip()
        if not key or not source_id:
            errors.append("current guidance item is missing key or source_id")
        if key in guidance_keys:
            errors.append(f"duplicate current guidance key {key!r}")
        guidance_keys.add(key)
        if source_id:
            source_ids.add(source_id)

    claim_keys: set[str] = set()
    for group in ("open_management_claims", "resolved_management_claims"):
        for item in snapshot.get(group) or []:
            key = str(item.get("key") or "").strip()
            source_id = str(item.get("source_id") or "").strip()
            if not key or not source_id:
                errors.append(f"{group} item is missing key or source_id")
            if key in claim_keys:
                errors.append(f"management claim {key!r} appears more than once")
            claim_keys.add(key)
            if source_id:
                source_ids.add(source_id)

    if announcement_count > 0 and not source_ids:
        warnings.append("coverage exists but no structured memory item retains a source_id")
    if announcement_count >= 2 and comparable_series == 0:
        warnings.append("multiple announcements exist but no repeated comparable KPI series")

    return {
        "ticker": snapshot.get("ticker"),
        "company": snapshot.get("company"),
        "coverage_status": status,
        "announcement_count": announcement_count,
        "coverage_days": coverage_days,
        "current_guidance_count": len(snapshot.get("current_guidance") or []),
        "metric_series_count": len(snapshot.get("metric_series") or []),
        "comparable_series_count": comparable_series,
        "calculated_series_count": calculated_series,
        "open_claim_count": len(snapshot.get("open_management_claims") or []),
        "resolved_claim_count": len(snapshot.get("resolved_management_claims") or []),
        "disclosure_gap_count": len(snapshot.get("disclosure_gaps") or []),
        "source_id_count": len(source_ids),
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate deterministic Smallcaps.ai Company Memory for one ticker."
    )
    parser.add_argument("--ticker", required=True, help="AIM ticker, for example SPR")
    parser.add_argument(
        "--include-snapshot",
        action="store_true",
        help="Include the complete Company Intelligence snapshot in JSON output.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("web")
    if errors:
        result = {
            "ticker": args.ticker.upper(),
            "valid": False,
            "errors": errors,
            "warnings": warnings,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    engine = create_database_engine(settings.database_url)
    try:
        repository = CompanyIntelligenceRepository(
            create_session_factory(engine)
        )
        snapshot = repository.get_company_intelligence(args.ticker)
        if snapshot is None:
            result = {
                "ticker": args.ticker.upper(),
                "valid": False,
                "errors": ["Ticker is not covered by a publishable Smallcaps.ai record."],
                "warnings": warnings,
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            raise SystemExit(1)
        result = validate_snapshot(snapshot)
        result["warnings"] = [*warnings, *result["warnings"]]
        if args.include_snapshot:
            result["snapshot"] = snapshot
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result["valid"]:
            raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
