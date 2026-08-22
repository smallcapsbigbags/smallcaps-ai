from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyst.intelligence_benchmark import (
    load_intelligence_cases,
    run_intelligence_benchmark,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the zero-token Analyst Intelligence regression benchmark."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/analyst_intelligence_cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("analyst-intelligence-results.json"),
    )
    args = parser.parse_args()

    cases = load_intelligence_cases(args.cases)
    payload = run_intelligence_benchmark(cases)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    acceptance = payload["acceptance"]
    print("[analyst-intelligence] " + json.dumps(acceptance), flush=True)
    for result in payload["results"]:
        print(
            "[analyst-intelligence] "
            f"{result['case_id']}: pass={result['passed']} "
            f"profile={result['actual_profile']} "
            f"findings={','.join(result['actual_finding_codes']) or 'none'}",
            flush=True,
        )
        for missing in result["missing_finding_codes"]:
            print(
                f"[analyst-intelligence]   missing: {missing}",
                flush=True,
            )
        for forbidden in result["forbidden_finding_codes_found"]:
            print(
                f"[analyst-intelligence]   forbidden: {forbidden}",
                flush=True,
            )
    if not acceptance["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
