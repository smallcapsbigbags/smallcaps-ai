from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from analyst.analyzer import OpenAIAnalystEngine
from analyst.classification import classify_metadata_type
from analyst.gold_standard import (
    GoldStandardEvaluator,
    benchmark_acceptance,
    headline_matches,
    load_real_benchmark_cases,
)
from analyst.guardrails import apply_analysis_guardrails
from analyst.quality import assess_analysis_quality
from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource
from settings import Settings


def _match_case(
    case,
    catalogue: list[CatalogueAnnouncement],
) -> CatalogueAnnouncement | None:
    ticker_matches = [item for item in catalogue if item.ticker.upper() == case.ticker.upper()]
    if not ticker_matches:
        return None
    headline_matches_list = [item for item in ticker_matches if headline_matches(case, item.title)]
    if headline_matches_list:
        return headline_matches_list[0]
    if len(ticker_matches) == 1:
        return ticker_matches[0]
    return None


def _load_active_case_ids(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("benchmark case set must be a JSON list of case IDs")
    if len(raw) != len(set(raw)):
        raise ValueError("benchmark case set contains duplicate IDs")
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Analyst 2.1 against the 20-case real-RNS human-grade benchmark."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/real_cases.json"),
    )
    parser.add_argument(
        "--case-set",
        type=Path,
        default=Path("benchmarks/real_case_set.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("gold-standard-results.json"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of active benchmark cases to run.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("benchmark")
    for warning in warnings:
        print(f"[benchmark] WARNING: {warning}", flush=True)
    if errors:
        raise RuntimeError("; ".join(errors))

    all_cases = load_real_benchmark_cases(args.cases)
    case_map = {case.id: case for case in all_cases}
    active_ids = _load_active_case_ids(args.case_set)
    missing_definitions = [case_id for case_id in active_ids if case_id not in case_map]
    if missing_definitions:
        raise ValueError(
            "active benchmark references undefined cases: "
            + ", ".join(missing_definitions)
        )
    cases = [case_map[case_id] for case_id in active_ids]
    if args.limit > 0:
        cases = cases[: args.limit]

    analyst = OpenAIAnalystEngine(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_output_tokens=settings.openai_max_output_tokens,
    )
    evaluator = GoldStandardEvaluator(
        api_key=settings.openai_api_key,
        model=settings.openai_deep_model,
    )
    source = InvestegateDailyAIMSource(
        api_key=settings.openai_api_key,
        deep_model=settings.openai_deep_model,
        deep_batch_size=settings.deep_search_batch_size,
        max_document_chars=settings.max_document_chars,
        max_pages=max(settings.investegate_aim_max_pages, 12),
    )

    cases_by_day: dict[date, list[object]] = defaultdict(list)
    for case in cases:
        cases_by_day[date.fromisoformat(case.day)].append(case)

    results: list[dict[str, object]] = []
    judgements = []
    missing_cases: list[str] = []
    failed_cases: list[str] = []

    for day in sorted(cases_by_day):
        print(f"[benchmark] Discovering AIM catalogue for {day.isoformat()}", flush=True)
        catalogue, discovery_warnings = source.list_announcements(day)
        for warning in discovery_warnings:
            print(f"[benchmark] source: {warning}", flush=True)

        matched: list[tuple[object, CatalogueAnnouncement]] = []
        for case in cases_by_day[day]:
            item = _match_case(case, catalogue)
            if item is None:
                missing_cases.append(case.id)
                print(
                    f"[benchmark] MISSING {case.id} ticker={case.ticker} "
                    f"headline_matchers={case.headline_contains}",
                    flush=True,
                )
                continue
            matched.append((case, item))
            print(
                f"[benchmark] matched {case.id}: {item.ticker} · {item.title}",
                flush=True,
            )

        source.prepare_documents([item for _case, item in matched])

        for case, item in matched:
            try:
                announcement = source.fetch_document(item)
                announcement = announcement.model_copy(
                    update={"rns_type": classify_metadata_type(item)}
                )
                note = analyst.analyse(announcement, case.prior_context)
                note = apply_analysis_guardrails(announcement, note)
                quality = assess_analysis_quality(
                    announcement,
                    note,
                    prior_context=case.prior_context,
                )
                judgement = evaluator.evaluate(
                    case=case,
                    announcement=announcement,
                    note=note,
                    prior_context=case.prior_context,
                )
                judgements.append(judgement)
                passed = judgement.passed and quality.status != "blocked"
                if not passed:
                    failed_cases.append(case.id)
                result = {
                    "case": case.model_dump(mode="json"),
                    "source": {
                        "source_id": announcement.source_id,
                        "title": announcement.title,
                        "source_urls": announcement.source_urls,
                    },
                    "quality": quality.model_dump(mode="json"),
                    "note": note.model_dump(mode="json"),
                    "judgement": {
                        **judgement.model_dump(mode="json"),
                        "total_score": judgement.total_score,
                        "passed": judgement.passed,
                    },
                }
                results.append(result)
                gaps = "; ".join(judgement.top_gaps[:2]) or "none"
                print(
                    f"[benchmark] {case.id}: score={judgement.total_score}/100 "
                    f"pass={passed} impact={note.impact_colour}/{note.impact_score} "
                    f"quality={quality.status} main_change={judgement.main_change_identified} "
                    f"gaps={gaps}",
                    flush=True,
                )
                for recommendation in judgement.upgrade_recommendations[:3]:
                    print(
                        f"[benchmark]   upgrade: {recommendation}",
                        flush=True,
                    )
                if judgement.critical_failures:
                    print(
                        f"[benchmark]   CRITICAL: {'; '.join(judgement.critical_failures)}",
                        flush=True,
                    )
            except Exception as exc:
                failed_cases.append(case.id)
                print(f"[benchmark] ERROR {case.id}: {exc}", flush=True)
                results.append(
                    {
                        "case": case.model_dump(mode="json"),
                        "error": str(exc),
                    }
                )

    acceptance = benchmark_acceptance(judgements)
    acceptance["expected_cases"] = len(cases)
    acceptance["scored_cases"] = len(judgements)
    acceptance["missing_cases"] = missing_cases
    acceptance["failed_cases"] = list(dict.fromkeys(failed_cases))
    if len(judgements) != len(cases) or missing_cases:
        acceptance["passed"] = False

    payload = {
        "analyst_model": settings.openai_model,
        "evidence_model": settings.openai_deep_model,
        "prompt_version": settings.prompt_version,
        "active_case_ids": [case.id for case in cases],
        "acceptance": acceptance,
        "results": results,
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("[benchmark] SUMMARY " + json.dumps(acceptance, ensure_ascii=False), flush=True)
    if not acceptance["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
