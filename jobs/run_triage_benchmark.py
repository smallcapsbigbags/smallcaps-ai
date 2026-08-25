from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analyst.models import AnnouncementInput
from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.triage import TriageContext, assess_light, initial_triage

LONDON = ZoneInfo("Europe/London")


def run(cases_path: Path) -> dict[str, object]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    failures: list[dict[str, str]] = []
    metadata_results: list[dict[str, str]] = []
    light_results: list[dict[str, str]] = []

    for index, case in enumerate(payload.get("metadata_cases", [])):
        item = CatalogueAnnouncement(
            source_id=f"triage-metadata-{index}",
            ticker="TST",
            company="Triage Benchmark plc",
            published_at=datetime(2026, 8, 25, 7, index % 60, tzinfo=LONDON),
            title=case["title"],
            source_url=f"https://example.invalid/triage/{index}",
        )
        actual = initial_triage(item).processing_level
        expected = case["expected"]
        result = {"id": case["id"], "expected": expected, "actual": actual}
        metadata_results.append(result)
        if actual != expected:
            failures.append(result)

    for index, case in enumerate(payload.get("light_cases", [])):
        item = CatalogueAnnouncement(
            source_id=f"triage-light-{index}",
            ticker="TST",
            company="Triage Benchmark plc",
            published_at=datetime(2026, 8, 25, 8, index % 60, tzinfo=LONDON),
            title=case["title"],
            source_url=f"https://example.invalid/light/{index}",
        )
        initial = initial_triage(item)
        context = TriageContext(**case.get("context", {}))
        announcement = AnnouncementInput(
            source_id=item.source_id,
            ticker=item.ticker,
            company=item.company,
            published_at=item.published_at,
            title=item.title,
            text=case["text"],
            source_url=item.source_url,
            source_urls=[item.source_url],
        )
        decision = assess_light(announcement, context=context, initial=initial)
        actual = decision.processing_level
        expected = case["expected"]
        result = {"id": case["id"], "expected": expected, "actual": actual}
        light_results.append(result)
        if actual != expected:
            failures.append(result)

    metadata_non_archive = sum(
        1 for item in metadata_results if item["expected"] != "ARCHIVE"
    )
    light_case_count = len(light_results)
    baseline_full_calls = metadata_non_archive + light_case_count
    new_full_calls = sum(
        1 for item in metadata_results if item["actual"] == "FULL"
    ) + sum(1 for item in light_results if item["actual"] == "FULL")
    reduction = (
        0.0
        if baseline_full_calls == 0
        else 1.0 - (new_full_calls / baseline_full_calls)
    )

    return {
        "version": payload.get("version", ""),
        "passed": not failures,
        "failure_count": len(failures),
        "metadata_cases": len(metadata_results),
        "light_cases": len(light_results),
        "baseline_full_analyst_calls": baseline_full_calls,
        "new_full_analyst_calls": new_full_calls,
        "estimated_full_analyst_call_reduction_pct": round(reduction * 100, 1),
        "failures": failures,
        "metadata_results": metadata_results,
        "light_results": light_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic newsroom triage benchmark.")
    parser.add_argument("--cases", default="benchmarks/triage_cases.json")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = run(Path(args.cases))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered, flush=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
