from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analyst.analyzer import OpenAIAnalystEngine
from analyst.evaluation import evaluate_benchmark, load_benchmark_cases
from analyst.models import AnnouncementInput
from settings import Settings

LONDON = ZoneInfo("Europe/London")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Analyst Engine 2.0 benchmark suite."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results.json"),
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for live benchmarks")

    engine = OpenAIAnalystEngine(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_output_tokens=settings.openai_max_output_tokens,
    )
    cases = load_benchmark_cases(args.cases)
    results: list[dict[str, object]] = []

    for index, case in enumerate(cases):
        announcement = AnnouncementInput(
            source_id=f"benchmark-{case.id}",
            ticker=case.ticker,
            company=case.company,
            published_at=datetime(
                2026,
                8,
                21,
                7,
                min(index, 59),
                tzinfo=LONDON,
            ),
            title=case.title,
            text=case.text,
            rns_type=case.rns_type,
            source_note="Canonical Analyst Engine benchmark case.",
            evidence_status="complete",
        )
        note = engine.analyse(announcement, case.prior_context)
        evaluation = evaluate_benchmark(case, note)
        results.append(
            {
                "case": case.model_dump(mode="json"),
                "note": note.model_dump(mode="json"),
                "evaluation": evaluation.model_dump(mode="json"),
            }
        )
        print(
            f"{case.id}: {'PASS' if evaluation.passed else 'FAIL'}"
        )

    args.output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    passed = sum(
        1 for result in results if result["evaluation"]["passed"]
    )
    print(f"Benchmark: {passed}/{len(results)} passed")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
