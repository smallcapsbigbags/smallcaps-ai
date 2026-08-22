from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyst.company_validation import validate_company_timeline
from database.company_validation import CompanyValidationRepository
from database.db import create_database_engine, create_session_factory
from settings import Settings


def _tickers(value: str) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in value.split(","):
        ticker = raw.upper().strip().replace(".L", "").rstrip(".-")
        if ticker and ticker not in seen:
            seen.add(ticker)
            output.append(ticker)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct live point-in-time Company Memory without making an AI call."
        )
    )
    parser.add_argument(
        "--tickers",
        default="SPR",
        help="Comma-separated priority tickers. Springfield is the Phase 3 anchor.",
    )
    parser.add_argument(
        "--auto",
        type=int,
        default=3,
        help="Add this many covered companies with deep/diverse RNS histories.",
    )
    parser.add_argument(
        "--minimum-history",
        type=int,
        default=2,
        help="Minimum publishable RNS records required for a live validation pass.",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=7,
        help="Exact prior RNS records supplied alongside the compact memory snapshot.",
    )
    parser.add_argument(
        "--timeline-limit",
        type=int,
        default=240,
        help="Maximum publishable records loaded for one company.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("company-memory-live-validation.json"),
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("web")
    if errors:
        payload = {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "reports": [],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
        raise SystemExit(1)

    engine = create_database_engine(settings.database_url)
    try:
        repository = CompanyValidationRepository(
            create_session_factory(engine)
        )
        selected = _tickers(args.tickers)
        explicit = set(selected)
        auto_target = max(0, args.auto)
        if auto_target:
            candidates = repository.list_candidates(
                min_announcements=max(1, args.minimum_history),
                limit=max(10, auto_target * 5),
                preferred_tickers=tuple(selected),
            )
            added = 0
            for candidate in candidates:
                ticker = str(candidate["ticker"])
                if ticker in explicit or ticker in selected:
                    continue
                selected.append(ticker)
                added += 1
                if added >= auto_target:
                    break

        reports: list[dict[str, object]] = []
        job_errors: list[str] = []
        minimum_history = max(1, args.minimum_history)
        for ticker in selected:
            timeline = repository.load_timeline(
                ticker,
                limit=max(1, args.timeline_limit),
            )
            if timeline is None:
                job_errors.append(f"{ticker}: company is not covered")
                continue
            count = int(timeline.get("announcement_count") or 0)
            if count < minimum_history:
                job_errors.append(
                    f"{ticker}: only {count} publishable RNS record(s); "
                    f"at least {minimum_history} are required"
                )
                continue
            report = validate_company_timeline(
                list(timeline.get("records") or []),
                ticker=ticker,
                company=str(timeline.get("company") or ticker),
                history_limit=max(0, args.history_limit),
            )
            reports.append(report)
            if not report["valid"]:
                job_errors.extend(
                    f"{ticker}: {message}"
                    for message in report.get("errors") or []
                )
            print(
                f"[company-memory-live] {ticker}: records={count} "
                f"event_types={report['event_type_count']} "
                f"valid={report['valid']} warnings={len(report['warnings'])}",
                flush=True,
            )

        summary = {
            "valid": bool(reports) and not job_errors,
            "requested_tickers": _tickers(args.tickers),
            "validated_tickers": [report["ticker"] for report in reports],
            "validated_company_count": len(reports),
            "valid_company_count": sum(
                1 for report in reports if bool(report["valid"])
            ),
            "checked_announcement_count": sum(
                int(report["checked_points"]) for report in reports
            ),
            "error_count": len(job_errors),
            "warning_count": sum(
                len(report.get("warnings") or []) for report in reports
            ),
            "errors": job_errors,
            "warnings": warnings,
            "reports": reports,
        }
        args.output.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            "[company-memory-live] SUMMARY "
            + json.dumps(
                {
                    key: value
                    for key, value in summary.items()
                    if key != "reports"
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if not summary["valid"]:
            raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
