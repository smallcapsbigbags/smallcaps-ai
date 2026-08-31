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
    GoldStandardJudgement,
    benchmark_acceptance,
    load_real_benchmark_cases,
)
from analyst.guardrails import apply_analysis_guardrails
from analyst.intelligence_policy import AnalystIntelligenceBundle, detect_analytical_tensions
from analyst.kpi_profiles import infer_kpi_profile
from analyst.quality import assess_analysis_quality
from analyst.routing_benchmark import (
    RoutingAuditRecord,
    RoutingRegressionEvaluator,
    routing_benchmark_acceptance,
)
from ingestion.investegate_daily import InvestegateDailyAIMSource
from jobs.run_gold_standard_benchmark import (
    _direct_target,
    _load_active_case_ids,
    _load_source_map,
    _match_case,
)
from settings import Settings


def _dimension_averages(
    judgements: list[GoldStandardJudgement],
) -> dict[str, float]:
    fields = (
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
    if not judgements:
        return {field: 0.0 for field in fields}
    return {
        field: round(
            sum(float(getattr(item, field)) for item in judgements) / len(judgements),
            2,
        )
        for field in fields
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Pass 4: compare Analyst 3.4 routed output with a forced legacy-style "
            "second consistency review on representative real AIM announcements."
        )
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/real_cases.json"),
    )
    parser.add_argument(
        "--case-set",
        type=Path,
        default=Path("benchmarks/pass4_routing_case_set.json"),
    )
    parser.add_argument(
        "--source-map",
        type=Path,
        default=Path("benchmarks/real_case_sources.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("routing-quality-results.json"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of active benchmark cases to run.",
    )
    parser.add_argument(
        "--min-single-pass-cases",
        type=int,
        default=2,
        help="Minimum one-pass cases required to prove that the cost route is exercised.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("benchmark")
    for warning in warnings:
        print(f"[pass4-routing] WARNING: {warning}", flush=True)
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
            "active Pass 4 benchmark references undefined cases: "
            + ", ".join(missing_definitions)
        )
    if missing_sources:
        raise ValueError(
            "active Pass 4 benchmark references cases without source metadata: "
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
    pairwise_evaluator = RoutingRegressionEvaluator(
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
    records: list[RoutingAuditRecord] = []
    routed_judgements: list[GoldStandardJudgement] = []
    failed_cases: list[str] = []
    direct_targets: list[str] = []
    non_publishable_cases: list[str] = []
    wrong_direction_cases: list[str] = []

    for day in sorted(cases_by_day):
        print(
            f"[pass4-routing] Discovering AIM catalogue for {day.isoformat()}",
            flush=True,
        )
        try:
            catalogue, discovery_warnings = source.list_announcements(day)
        except Exception as exc:
            catalogue, discovery_warnings = [], [
                f"Historical catalogue discovery unavailable ({exc}); using direct benchmark targets."
            ]
        for warning in discovery_warnings:
            print(f"[pass4-routing] source: {warning}", flush=True)

        matched: list[tuple[object, object]] = []
        for case in cases_by_day[day]:
            item = _match_case(case, catalogue)
            if item is None:
                item = _direct_target(case, source_map)
                direct_targets.append(case.id)
                print(
                    f"[pass4-routing] direct-target {case.id}: {item.ticker} · {item.title}",
                    flush=True,
                )
            else:
                print(
                    f"[pass4-routing] catalogue-match {case.id}: {item.ticker} · {item.title}",
                    flush=True,
                )
            matched.append((case, item))

        source.prepare_documents([item for _case, item in matched])

        for case, item in matched:
            try:
                announcement = source.fetch_document(item)
                announcement = announcement.model_copy(
                    update={"rns_type": classify_metadata_type(item)}
                )
                print(
                    f"[pass4-routing] Analysing {case.id} evidence_chars={len(announcement.text)}",
                    flush=True,
                )

                routed_raw = analyst.analyse(announcement, case.prior_context)
                decision = analyst.last_review_decision
                if decision is None:
                    raise RuntimeError("Analyst returned no routing decision")

                routed_note = apply_analysis_guardrails(announcement, routed_raw)
                routed_quality = assess_analysis_quality(
                    announcement,
                    routed_note,
                    prior_context=case.prior_context,
                )
                routed_judgement = evaluator.evaluate(
                    case=case,
                    announcement=announcement,
                    note=routed_note,
                    prior_context=case.prior_context,
                )
                routed_judgements.append(routed_judgement)

                if routed_quality.status != "publishable":
                    non_publishable_cases.append(case.id)
                if routed_judgement.impact_alignment == "wrong-direction":
                    wrong_direction_cases.append(case.id)

                shadow_note = None
                shadow_quality = None
                shadow_judgement = None
                pairwise = None

                if decision.mode == "single-pass":
                    profile = infer_kpi_profile(announcement, case.prior_context)
                    findings = detect_analytical_tensions(
                        announcement,
                        routed_raw,
                        case.prior_context,
                        profile=profile,
                    )
                    intelligence = AnalystIntelligenceBundle(
                        profile=profile,
                        findings=findings,
                    )
                    # Benchmark-only shadow call. This deliberately invokes the same
                    # second-pass code path that Analyst 3.3 paid for on every full case.
                    shadow_raw = analyst._review_note(
                        announcement=announcement,
                        prior_context=case.prior_context,
                        draft=routed_raw,
                        intelligence=intelligence,
                    )
                    shadow_note = apply_analysis_guardrails(announcement, shadow_raw)
                    shadow_quality = assess_analysis_quality(
                        announcement,
                        shadow_note,
                        prior_context=case.prior_context,
                    )
                    shadow_judgement = evaluator.evaluate(
                        case=case,
                        announcement=announcement,
                        note=shadow_note,
                        prior_context=case.prior_context,
                    )
                    pairwise = pairwise_evaluator.compare(
                        case=case,
                        announcement=announcement,
                        routed_note=routed_note,
                        reviewed_note=shadow_note,
                        prior_context=case.prior_context,
                    )

                routed_gold_passed = (
                    routed_judgement.passed
                    and routed_quality.status == "publishable"
                )
                if not routed_gold_passed:
                    failed_cases.append(case.id)

                record = RoutingAuditRecord(
                    case_id=case.id,
                    decision_mode=decision.mode,
                    decision_reasons=list(decision.reasons),
                    routed_publishable=routed_quality.status == "publishable",
                    routed_gold_passed=routed_gold_passed,
                    routed_score=routed_judgement.total_score,
                    routed_factual_grounding=routed_judgement.factual_grounding,
                    routed_critical_failures=routed_judgement.critical_failures,
                    routed_impact_alignment=routed_judgement.impact_alignment,
                    routed_impact_colour=routed_note.impact_colour,
                    routed_impact_score=routed_note.impact_score,
                    shadow_reviewed=shadow_note is not None,
                    shadow_publishable=(
                        shadow_quality.status == "publishable"
                        if shadow_quality is not None
                        else None
                    ),
                    shadow_gold_passed=(
                        shadow_judgement.passed
                        and shadow_quality is not None
                        and shadow_quality.status == "publishable"
                        if shadow_judgement is not None
                        else None
                    ),
                    shadow_score=(
                        shadow_judgement.total_score
                        if shadow_judgement is not None
                        else None
                    ),
                    shadow_factual_grounding=(
                        shadow_judgement.factual_grounding
                        if shadow_judgement is not None
                        else None
                    ),
                    shadow_impact_colour=(
                        shadow_note.impact_colour if shadow_note is not None else None
                    ),
                    shadow_impact_score=(
                        shadow_note.impact_score if shadow_note is not None else None
                    ),
                    pairwise_acceptable=(
                        pairwise.acceptable_single_pass if pairwise is not None else None
                    ),
                    pairwise_material_regressions=(
                        pairwise.material_regressions if pairwise is not None else []
                    ),
                )
                records.append(record)

                result = {
                    "case": case.model_dump(mode="json"),
                    "source": {
                        "source_id": announcement.source_id,
                        "title": announcement.title,
                        "source_urls": announcement.source_urls,
                        "direct_target": case.id in direct_targets,
                    },
                    "routing": {
                        "mode": decision.mode,
                        "reasons": list(decision.reasons),
                        "policy_version": decision.policy_version,
                    },
                    "routed": {
                        "quality": routed_quality.model_dump(mode="json"),
                        "note": routed_note.model_dump(mode="json"),
                        "judgement": {
                            **routed_judgement.model_dump(mode="json"),
                            "total_score": routed_judgement.total_score,
                            "passed": routed_judgement.passed,
                        },
                    },
                    "shadow_review": (
                        {
                            "quality": shadow_quality.model_dump(mode="json"),
                            "note": shadow_note.model_dump(mode="json"),
                            "judgement": {
                                **shadow_judgement.model_dump(mode="json"),
                                "total_score": shadow_judgement.total_score,
                                "passed": shadow_judgement.passed,
                            },
                            "pairwise": pairwise.model_dump(mode="json"),
                        }
                        if shadow_note is not None
                        and shadow_quality is not None
                        and shadow_judgement is not None
                        and pairwise is not None
                        else None
                    ),
                    "audit_record": record.model_dump(mode="json"),
                }
                results.append(result)

                shadow_text = ""
                if shadow_judgement is not None and pairwise is not None:
                    shadow_text = (
                        f" shadow={shadow_judgement.total_score}/100 "
                        f"pairwise_ok={pairwise.acceptable_single_pass}"
                    )
                print(
                    f"[pass4-routing] {case.id}: route={decision.mode} "
                    f"routed={routed_judgement.total_score}/100 "
                    f"quality={routed_quality.status} "
                    f"impact={routed_note.impact_colour}/{routed_note.impact_score}"
                    f"{shadow_text}",
                    flush=True,
                )
            except Exception as exc:
                failed_cases.append(case.id)
                print(f"[pass4-routing] ERROR {case.id}: {exc}", flush=True)
                results.append(
                    {
                        "case": case.model_dump(mode="json"),
                        "error": str(exc),
                    }
                )

    gold_acceptance = benchmark_acceptance(routed_judgements)
    gold_acceptance["expected_cases"] = len(cases)
    gold_acceptance["scored_cases"] = len(routed_judgements)
    gold_acceptance["failed_cases"] = list(dict.fromkeys(failed_cases))
    gold_acceptance["non_publishable_cases"] = list(
        dict.fromkeys(non_publishable_cases)
    )
    gold_acceptance["wrong_direction_cases"] = list(
        dict.fromkeys(wrong_direction_cases)
    )
    gold_acceptance["dimension_averages"] = _dimension_averages(routed_judgements)
    if (
        len(routed_judgements) != len(cases)
        or failed_cases
        or non_publishable_cases
        or wrong_direction_cases
    ):
        gold_acceptance["passed"] = False

    routing_acceptance = routing_benchmark_acceptance(
        records,
        expected_cases=len(cases),
        min_single_pass_cases=max(0, args.min_single_pass_cases),
    )
    passed = bool(gold_acceptance["passed"] and routing_acceptance["passed"])

    payload = {
        "benchmark": "facts-no-fluff-pass4-routing-quality-v1",
        "analyst_model": settings.openai_model,
        "evidence_model": settings.openai_deep_model,
        "prompt_version": settings.prompt_version,
        "active_case_ids": [case.id for case in cases],
        "direct_target_cases": direct_targets,
        "passed": passed,
        "gold_standard_acceptance": gold_acceptance,
        "routing_acceptance": routing_acceptance,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        "[pass4-routing] GOLD " + json.dumps(gold_acceptance, ensure_ascii=False),
        flush=True,
    )
    print(
        "[pass4-routing] ROUTING "
        + json.dumps(routing_acceptance, ensure_ascii=False),
        flush=True,
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
