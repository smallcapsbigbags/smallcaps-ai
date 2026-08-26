from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from product.radar import RadarObservation, detect_radar_setups


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    observation = RadarObservation.model_validate(case["observation"])
    setups = detect_radar_setups(observation)
    actual_types = [setup.setup_type for setup in setups]
    expected_types = list(case.get("expected_types") or [])
    errors: list[str] = []
    if actual_types != expected_types:
        errors.append(f"expected_types={expected_types!r} actual_types={actual_types!r}")
    for setup in setups:
        if not setup.evidence:
            errors.append(f"{setup.setup_type} has no evidence")
        if setup.setup_score < 50:
            errors.append(f"{setup.setup_type} score is too low: {setup.setup_score}")
        if not setup.primary_source_id:
            errors.append(f"{setup.setup_type} missing primary_source_id")
    return {
        "case_id": str(case.get("case_id") or "unknown"),
        "passed": not errors,
        "errors": errors,
        "actual_types": actual_types,
        "scores": {setup.setup_type: setup.setup_score for setup in setups},
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
    parser = argparse.ArgumentParser(description="Run the AIM Radar setup benchmark.")
    parser.add_argument("--cases", default="benchmarks/radar_cases.json")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = run_benchmark(Path(args.cases))
    print(
        "[aim-radar] "
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
            f"[aim-radar] {case['case_id']}: pass={case['passed']} "
            f"setups={case['actual_types']} scores={case['scores']}",
            flush=True,
        )
        for error in case["errors"]:
            print(f"[aim-radar] ERROR {case['case_id']}: {error}", flush=True)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
