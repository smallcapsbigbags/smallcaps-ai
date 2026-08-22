from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyst.analyzer import OpenAIAnalystEngine
from analyst.company_memory import build_company_memory
from analyst.company_memory_evaluation import (
    CompanyMemoryEvaluator,
    company_memory_acceptance,
    load_company_memory_cases,
)
from analyst.guardrails import apply_analysis_guardrails
from analyst.quality import assess_analysis_quality
from settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Analyst 3.0 against the locked Company Memory regression set."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/company_memory_cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("company-memory-benchmark-results.json"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of cases to run.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("benchmark")
    for warning in warnings:
        print(f"[company-memory] WARNING: {warning}", flush=True)
    if errors:
        raise RuntimeError("; ".join(errors))

    cases = load_company_memory_cases(args.cases)
    if args.limit > 0:
        cases = cases[: args.limit]

    analyst = OpenAIAnalystEngine(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_output_tokens=settings.openai_max_output_tokens,
    )
    evaluator = CompanyMemoryEvaluator(
        api_key=settings.openai_api_key,
        model=settings.openai_deep_model,
    )

    results: list[dict[str, object]] = []
    judgements = []
    failed_cases: list[str] = []

    for case in cases:
        announcement = case.current_announcement
        snapshot = build_company_memory(
            case.history,
            ticker=case.ticker,
            company=case.company,
            before=announcement.published_at,
        )
        context = [snapshot.to_context_record(), *case.history[-7:]]
        try:
            print(
                f"[company-memory] Analysing {case.id} with "
                f"{snapshot.announcement_count} prior RNS record(s)",
                flush=True,
            )
            note = analyst.analyse(announcement, context)
            note = apply_analysis_guardrails(
                announcement,
                note,
                prior_context=context,
            )
            quality = assess_analysis_quality(
                announcement,
                note,
                prior_context=context,
            )
            judgement = evaluator.evaluate(
                case=case,
                snapshot=snapshot,
                note=note,
                quality_status=quality.status,
            )
            judgements.append(judgement)
            passed = judgement.passed and quality.status == "publishable"
            if not passed:
                failed_cases.append(case.id)
            results.append(
                {
                    "case": case.model_dump(mode="json"),
                    "memory_snapshot": snapshot.model_dump(mode="json"),
                    "note": note.model_dump(mode="json"),
                    "quality": quality.model_dump(mode="json"),
                    "judgement": {
                        **judgement.model_dump(mode="json"),
                        "total_score": judgement.total_score,
                        "passed": judgement.passed,
                    },
                }
            )
            gaps = "; ".join(judgement.top_gaps[:2]) or "none"
            print(
                f"[company-memory] {case.id}: score={judgement.total_score}/100 "
                f"pass={passed} quality={quality.status} "
                f"impact={note.impact_colour}/{note.impact_score} "
                f"case_change={judgement.assessed_case_change} gaps={gaps}",
                flush=True,
            )
            for recommendation in judgement.upgrade_recommendations[:3]:
                print(
                    f"[company-memory]   upgrade: {recommendation}",
                    flush=True,
                )
            for failure in judgement.critical_failures:
                print(
                    f"[company-memory]   CRITICAL: {failure}",
                    flush=True,
                )
        except Exception as exc:
            failed_cases.append(case.id)
            print(f"[company-memory] ERROR {case.id}: {exc}", flush=True)
            results.append(
                {
                    "case": case.model_dump(mode="json"),
                    "memory_snapshot": snapshot.model_dump(mode="json"),
                    "error": str(exc),
                }
            )

    acceptance = company_memory_acceptance(judgements)
    acceptance["scored_cases"] = len(judgements)
    acceptance["requested_cases"] = len(cases)
    acceptance["failed_cases"] = list(dict.fromkeys(failed_cases))
    acceptance["all_publishable"] = not failed_cases
    if len(judgements) != len(cases) or failed_cases:
        acceptance["passed"] = False

    payload = {
        "analyst_model": settings.openai_model,
        "evaluator_model": settings.openai_deep_model,
        "prompt_version": settings.prompt_version,
        "acceptance": acceptance,
        "results": results,
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        "[company-memory] SUMMARY "
        + json.dumps(acceptance, ensure_ascii=False),
        flush=True,
    )
    if not acceptance["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
