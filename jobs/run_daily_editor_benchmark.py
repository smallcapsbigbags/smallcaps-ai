from __future__ import annotations

import argparse
import json
from datetime import date, time
from pathlib import Path
from typing import Any

from product.daily_editor import DailyEditorCandidate, build_daily_editor


def _story_list(page) -> list:
    return [
        *([page.lead] if page.lead is not None else []),
        *page.also_matters,
        *page.quick_takes,
    ]


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        DailyEditorCandidate.model_validate(item)
        for item in list(case.get("candidates") or [])
    ]
    day = date.fromisoformat(str(case["date"]))
    cutoff = time.fromisoformat(str(case.get("cutoff") or "12:00"))
    page = build_daily_editor(day=day, cutoff=cutoff, candidates=candidates)
    expected = dict(case.get("expected") or {})

    actual_lead = page.lead.primary_source_id if page.lead is not None else None
    actual_also = [item.primary_source_id for item in page.also_matters]
    actual_quick = [item.primary_source_id for item in page.quick_takes]
    surfaced = {
        source_id
        for story in _story_list(page)
        for source_id in story.source_ids
    }

    errors: list[str] = []
    if actual_lead != expected.get("lead"):
        errors.append(
            f"lead expected={expected.get('lead')!r} actual={actual_lead!r}"
        )
    if actual_also != list(expected.get("also_matters") or []):
        errors.append(
            f"also_matters expected={expected.get('also_matters')!r} actual={actual_also!r}"
        )
    if actual_quick != list(expected.get("quick_takes") or []):
        errors.append(
            f"quick_takes expected={expected.get('quick_takes')!r} actual={actual_quick!r}"
        )

    unexpected_surfaced = [
        source_id
        for source_id in list(expected.get("suppressed") or [])
        if source_id in surfaced
    ]
    if unexpected_surfaced:
        errors.append(f"suppressed source(s) surfaced: {unexpected_surfaced}")

    if page.quiet_morning is not bool(expected.get("quiet_morning")):
        errors.append(
            f"quiet_morning expected={expected.get('quiet_morning')!r} actual={page.quiet_morning!r}"
        )

    expected_other = int(expected.get("other_analysed_count") or 0)
    if page.other_analysed_count != expected_other:
        errors.append(
            f"other_analysed_count expected={expected_other} actual={page.other_analysed_count}"
        )

    stories_by_ticker = {story.ticker: story for story in _story_list(page)}
    for ticker, source_ids in dict(expected.get("grouped_sources") or {}).items():
        story = stories_by_ticker.get(str(ticker).upper())
        if story is None:
            errors.append(f"grouped ticker {ticker} was not surfaced")
            continue
        if set(story.source_ids) != set(source_ids):
            errors.append(
                f"grouped {ticker} expected={sorted(source_ids)!r} actual={sorted(story.source_ids)!r}"
            )

    return {
        "case_id": str(case.get("case_id") or "unknown"),
        "passed": not errors,
        "errors": errors,
        "actual": {
            "lead": actual_lead,
            "also_matters": actual_also,
            "quick_takes": actual_quick,
            "quiet_morning": page.quiet_morning,
            "candidate_count": page.candidate_count,
            "published_story_count": page.published_story_count,
            "other_analysed_count": page.other_analysed_count,
            "priority_scores": {
                story.primary_source_id: story.priority_score
                for story in _story_list(page)
            },
        },
    }


def run_benchmark(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [evaluate_case(case) for case in list(payload.get("cases") or [])]
    failures = [case for case in cases if not case["passed"]]
    return {
        "schema_version": str(payload.get("schema_version") or ""),
        "passed": not failures,
        "case_count": len(cases),
        "passed_cases": len(cases) - len(failures),
        "failed_cases": [case["case_id"] for case in failures],
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AIM Daily editor benchmark.")
    parser.add_argument(
        "--cases",
        default="benchmarks/aim_daily_editor_cases.json",
        help="Path to the curated historical AIM morning cases.",
    )
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    report = run_benchmark(Path(args.cases))
    print(
        "[aim-daily-editor] "
        + json.dumps(
            {
                "passed": report["passed"],
                "case_count": report["case_count"],
                "passed_cases": report["passed_cases"],
                "failed_cases": report["failed_cases"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    for case in report["cases"]:
        print(
            f"[aim-daily-editor] {case['case_id']}: pass={case['passed']} "
            f"lead={case['actual']['lead']} "
            f"also={case['actual']['also_matters']} "
            f"quick={case['actual']['quick_takes']}",
            flush=True,
        )
        for error in case["errors"]:
            print(f"[aim-daily-editor] ERROR {case['case_id']}: {error}", flush=True)

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
