from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analyst.analyzer import OpenAIAnalystEngine
from analyst.classification import classify_metadata_type
from analyst.gold_standard import (
    GoldStandardEvaluator,
    GoldStandardJudgement,
    benchmark_acceptance,
    headline_matches,
    load_real_benchmark_cases,
)
from analyst.guardrails import apply_analysis_guardrails
from analyst.quality import assess_analysis_quality
from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource
from settings import Settings

LONDON = ZoneInfo("Europe/London")
_SCORE_FIELDS = (
    "factual_grounding",
    "investor_relevance",
    "comparator_discipline",
    "useful_calculations",
    "commercial_interpretation",
    "sector_event_kpi",
    "balance_sheet_capital_control",
    "uncertainty_and_explanation",
    "investment_case_change",
    "repeatability_and_next_steps",
    "plain_english",
)


def _match_case(
    case,
    catalogue: list[CatalogueAnnouncement],
) -> CatalogueAnnouncement | None:
    ticker_matches = [item for item in catalogue if item.ticker.upper() == case.ticker.upper()]
    if not ticker_matches:
        return None
    headline_matches_list = [
        item for item in ticker_matches if headline_matches(case, item.title)
    ]
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


def _load_source_map(path: Path) -> dict[str, dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("benchmark source map must be a JSON object")
    output: dict[str, dict[str, str]] = {}
    for case_id, metadata in raw.items():
        if not isinstance(metadata, dict):
            raise ValueError(f"source metadata for {case_id} must be an object")
        company = str(metadata.get("company") or "").strip()
        title = str(metadata.get("title") or "").strip()
        if not company or not title:
            raise ValueError(f"source metadata for {case_id} needs company and title")
        output[str(case_id)] = {"company": company, "title": title}
    return output


def _direct_target(case, source_map: dict[str, dict[str, str]]) -> CatalogueAnnouncement:
    metadata = source_map.get(case.id)
    if metadata is None:
        raise ValueError(f"no direct source metadata for benchmark case {case.id}")
    return CatalogueAnnouncement(
        source_id=f"benchmark-real-{case.id}",
        ticker=case.ticker,
        company=metadata["company"],
        published_at=datetime.combine(
            date.fromisoformat(case.day),
            datetime.min.time(),
            tzinfo=LONDON,
        ).replace(hour=7),
        title=metadata["title"],
        source_url="",
        categories=[],
    )


def _dimension_averages(
    judgements: list[GoldStandardJudgement],
) -> dict[str, float]:
    if not judgements:
        return {field: 0.0 for field in _SCORE_FIELDS}
    return {
        field: round(
            sum(float(getattr(item, field)) for item in judgements) / len(judgements),
            2,
        )
        for field in _SCORE_FIELDS
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Analyst 2.2 against the locked 20-case real-RNS human-grade benchmark."
    )
    parser.add_argument(
        "--cases", type=Path, default=Path("benchmarks/real_cases.json")
    )
    parser.add_argument(
        "--case-set", type=Path, default=Path("benchmarks/real_case_set.json")
    )
    parser.add_argument(
        "--source-map",
        type=Path,
        default=Path("benchmarks/real_case_sources.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("gold-standard-results.json")
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
    source_map = _load_source_map(args.source_map)
    missing_definitions = [case_id for case_id in active_ids if case_id not in case_map]
    missing_sources = [case_id for case_id in active_ids if case_id not in source_map]
    if missing_definitions:
        raise ValueError(
            "active benchmark references undefined cases: "
            + ", ".join(missing_definitions)
        )
    if missing_sources:
        raise ValueError(
            "active benchmark references cases without source metadata: "
            + ", ".join(missing_sources)
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
    judgements: list[GoldStandardJudgement] = []
    failed_cases: list[str] = []
    direct_targets: list[str] = []
    non_publishable_cases: list[str] = []
    wrong_direction_cases: list[str] = []
    impact_aligned_cases: list[str] = []

    for day in sorted(cases_by_day):
        print(f"[benchmark] Discovering AIM catalogue for {day.isoformat()}", flush=True)
        try:
            catalogue, discovery_warnings = source.list_announcements(day)
        except Exception as exc:
            catalogue, discovery_warnings = [], [
                f"Historical catalogue discovery unavailable ({exc}); using direct benchmark targets."
            ]
        for warning in discovery_warnings:
            print(f"[benchmark] source: {warning}", flush=True)

        matched: list[tuple[object, CatalogueAnnouncement]] = []
        for case in cases_by_day[day]:
            item = _match_case(case, catalogue)
            if item is None:
                item = _direct_target(case, source_map)
                direct_targets.append(case.id)
                print(
                    f"[benchmark] direct-target {case.id}: {item.ticker} · {item.title} · {case.day}",
                    flush=True,
                )
            else:
                print(
                    f"[benchmark] catalogue-match {case.id}: {item.ticker} · {item.title}",
                    flush=True,
                )
            matched.append((case, item))

        print(
            f"[benchmark] Retrieving evidence for {len(matched)} case(s) on {day.isoformat()}",
            flush=True,
        )
        source.prepare_documents([item for _case, item in matched])

        for case, item in matched:
            try:
                announcement = source.fetch_document(item)
                announcement = announcement.model_copy(
                    update={"rns_type": classify_metadata_type(item)}
                )
                print(
                    f"[benchmark] Analysing {case.id} evidence_chars={len(announcement.text)}",
                    flush=True,
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

                if quality.status != "publishable":
                    non_publishable_cases.append(case.id)
                if judgement.impact_alignment == "wrong-direction":
                    wrong_direction_cases.append(case.id)
                if judgement.impact_alignment == "aligned":
                    impact_aligned_cases.append(case.id)

                passed = judgement.passed and quality.status == "publishable"
                if not passed:
                    failed_cases.append(case.id)

                result = {
                    "case": case.model_dump(mode="json"),
                    "source": {
                        "source_id": announcement.source_id,
                        "title": announcement.title,
                        "source_urls": announcement.source_urls,
                        "direct_target": case.id in direct_targets,
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
                    f"impact_alignment={judgement.impact_alignment} "
                    f"case_change={judgement.assessed_case_change} "
                    f"quality={quality.status} main_change={judgement.main_change_identified} "
                    f"gaps={gaps}",
                    flush=True,
                )
                if quality.status != "publishable":
                    for flag in quality.flags:
                        print(
                            f"[benchmark]   quality-{flag.severity}: {flag.code} — {flag.message}",
                            flush=True,
                        )
                for recommendation in judgement.upgrade_recommendations[:3]:
                    print(f"[benchmark]   upgrade: {recommendation}", flush=True)
                if judgement.critical_failures:
                    print(
                        f"[benchmark]   CRITICAL: {'; '.join(judgement.critical_failures)}",
                        flush=True,
                    )
            except Exception as exc:
                failed_cases.append(case.id)
                non_publishable_cases.append(case.id)
                print(f"[benchmark] ERROR {case.id}: {exc}", flush=True)
                results.append({"case": case.model_dump(mode="json"), "error": str(exc)})

    acceptance = benchmark_acceptance(judgements)
    acceptance["expected_cases"] = len(cases)
    acceptance["scored_cases"] = len(judgements)
    acceptance["direct_target_cases"] = direct_targets
    acceptance["failed_cases"] = list(dict.fromkeys(failed_cases))
    acceptance["non_publishable_cases"] = list(dict.fromkeys(non_publishable_cases))
    acceptance["wrong_direction_cases"] = list(dict.fromkeys(wrong_direction_cases))
    acceptance["impact_aligned_count"] = len(impact_aligned_cases)
    acceptance["dimension_averages"] = _dimension_averages(judgements)

    # A human-grade public analyst must pass both analytical scoring and the
    # deterministic publication gate. Impact direction must also be reliable.
    if (
        len(judgements) != len(cases)
        or non_publishable_cases
        or wrong_direction_cases
        or len(impact_aligned_cases) < max(0, len(cases) - 2)
    ):
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

    print(
        "[benchmark] DIMENSIONS "
        + json.dumps(acceptance["dimension_averages"], ensure_ascii=False),
        flush=True,
    )
    print("[benchmark] SUMMARY " + json.dumps(acceptance, ensure_ascii=False), flush=True)
    if not acceptance["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
