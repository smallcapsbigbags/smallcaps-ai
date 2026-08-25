from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from product.daily_editor import (
    CANONICAL_EDITION_CUTOFFS,
    DailyEditorCandidate,
    build_daily_editor,
    build_daily_editor_timeline,
)


def _visible_before(candidate: DailyEditorCandidate, state: str) -> bool:
    cutoff = CANONICAL_EDITION_CUTOFFS[state]  # type: ignore[index]
    local_time = candidate.published_at.timetz().replace(tzinfo=None)
    return local_time < cutoff


def _sources_for_lead(page) -> list[str]:
    return list(page.lead.source_ids) if page.lead is not None else []


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    day = date.fromisoformat(str(case["date"]))
    all_candidates = [
        DailyEditorCandidate.model_validate(item)
        for item in list(case.get("candidates") or [])
    ]
    editions = []
    for state in ("early_read", "morning_note", "aim_close"):
        editions.append(
            build_daily_editor(
                day=day,
                edition_state=state,
                candidates=[
                    item for item in all_candidates if _visible_before(item, state)
                ],
            )
        )
    timeline = build_daily_editor_timeline(day=day, editions=editions)
    expected = dict(case.get("expected") or {})
    errors: list[str] = []

    by_state = {page.edition_state: page for page in editions}
    for state in ("early_read", "morning_note", "aim_close"):
        page = by_state[state]
        state_expected = dict(expected.get(state) or {})
        if "lead" in state_expected:
            actual_lead = page.lead.primary_source_id if page.lead is not None else None
            if actual_lead != state_expected.get("lead"):
                errors.append(
                    f"{state} lead expected={state_expected.get('lead')!r} actual={actual_lead!r}"
                )
        if "also" in state_expected:
            actual_also = [story.primary_source_id for story in page.also_matters]
            if actual_also != list(state_expected.get("also") or []):
                errors.append(
                    f"{state} also expected={state_expected.get('also')!r} actual={actual_also!r}"
                )
        if "source_count" in state_expected:
            actual_count = len(_sources_for_lead(page))
            if actual_count != int(state_expected["source_count"]):
                errors.append(
                    f"{state} lead source_count expected={state_expected['source_count']} actual={actual_count}"
                )

    actual_statuses = [item.status for item in timeline.transitions]
    expected_statuses = list(expected.get("transition_statuses") or [])
    if actual_statuses != expected_statuses:
        errors.append(
            f"transition_statuses expected={expected_statuses!r} actual={actual_statuses!r}"
        )

    return {
        "case_id": str(case.get("case_id") or "unknown"),
        "passed": not errors,
        "errors": errors,
        "actual": {
            "states": {
                state: {
                    "lead": (
                        by_state[state].lead.primary_source_id
                        if by_state[state].lead is not None
                        else None
                    ),
                    "also": [
                        item.primary_source_id for item in by_state[state].also_matters
                    ],
                    "quick": [
                        item.primary_source_id for item in by_state[state].quick_takes
                    ],
                    "candidate_count": by_state[state].candidate_count,
                    "developing_story_count": by_state[state].developing_story_count,
                }
                for state in ("early_read", "morning_note", "aim_close")
            },
            "transition_statuses": actual_statuses,
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
    parser = argparse.ArgumentParser(
        description="Run the AIM Daily edition-state evolution benchmark."
    )
    parser.add_argument(
        "--cases",
        default="benchmarks/aim_daily_editor_evolution_cases.json",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = run_benchmark(Path(args.cases))
    print(
        "[aim-daily-evolution] "
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
            f"[aim-daily-evolution] {case['case_id']}: pass={case['passed']} "
            f"transitions={case['actual']['transition_statuses']}",
            flush=True,
        )
        for error in case["errors"]:
            print(
                f"[aim-daily-evolution] ERROR {case['case_id']}: {error}",
                flush=True,
            )

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
