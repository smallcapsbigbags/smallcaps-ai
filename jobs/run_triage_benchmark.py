from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analyst.triage import TriageContext, triage_evidence, triage_metadata
from ingestion.investegate_daily import CatalogueAnnouncement

LONDON = ZoneInfo("Europe/London")


def _item(case_id: str, title: str, index: int) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id=f"triage-{case_id}",
        ticker="TST",
        company="Triage Benchmark plc",
        published_at=datetime(2026, 8, 25, 7, index % 60, tzinfo=LONDON),
        title=title,
        source_url=f"https://example.invalid/triage/{case_id}",
    )


def run(
    metadata_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    metadata_cases = json.loads(metadata_path.read_text(encoding="utf-8"))
    evidence_cases = json.loads(evidence_path.read_text(encoding="utf-8"))

    failures: list[dict[str, str]] = []
    metadata_results: list[dict[str, str]] = []
    evidence_results: list[dict[str, str]] = []

    for index, case in enumerate(metadata_cases):
        item = _item(case["id"], case["title"], index)
        decision = triage_metadata(item)
        actual = decision.processing_level
        expected = case["expected"]
        result = {"id": case["id"], "expected": expected, "actual": actual}
        metadata_results.append(result)
        if actual != expected:
            failures.append(result)

    for index, case in enumerate(evidence_cases):
        item = _item(case["id"], case["title"], index)
        context = TriageContext(**case.get("context", {}))
        decision = triage_evidence(item, case["text"], context=context)
        actual = decision.processing_level
        expected = case["expected"]
        result = {"id": case["id"], "expected": expected, "actual": actual}
        evidence_results.append(result)
        if actual != expected:
            failures.append(result)

    # Proxy the expensive Analyst 3.3 stage rather than total OpenAI spend. Under
    # the old full-analysis policy every case would consume a full analyst call.
    # ARCHIVE consumes none; LIGHT consumes evidence retrieval only; FULL consumes
    # the complete Analyst 3.3 + review pipeline.
    baseline_full_calls = len(metadata_results) + len(evidence_results)
    projected_full_calls = sum(
        result["actual"] == "full"
        for result in [*metadata_results, *evidence_results]
    )
    reduction = (
        0.0
        if baseline_full_calls == 0
        else 1.0 - projected_full_calls / baseline_full_calls
    )

    return {
        "passed": not failures,
        "failure_count": len(failures),
        "metadata_cases": len(metadata_results),
        "evidence_cases": len(evidence_results),
        "baseline_full_analyst_calls": baseline_full_calls,
        "projected_full_analyst_calls": projected_full_calls,
        "estimated_full_analyst_call_reduction_pct": round(reduction * 100, 1),
        "failures": failures,
        "metadata_results": metadata_results,
        "evidence_results": evidence_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic Archive/Light/Full newsroom triage benchmark."
    )
    parser.add_argument("--metadata", default="benchmarks/triage_cases.json")
    parser.add_argument("--evidence", default="benchmarks/triage_evidence_cases.json")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = run(Path(args.metadata), Path(args.evidence))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered, flush=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
