from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from product.daily_editor import DailyEditorStory
from product.newsroom import (
    NewsroomFact,
    NewsroomGuidance,
    NewsroomMetricHistory,
    NewsroomStoryPacket,
    build_newsroom_article,
)


def _packet(case: dict[str, Any]) -> NewsroomStoryPacket:
    payload = dict(case.get("packet") or {})
    return NewsroomStoryPacket(
        story=DailyEditorStory.model_validate(payload["story"]),
        facts=[NewsroomFact.model_validate(item) for item in list(payload.get("facts") or [])],
        guidance=[NewsroomGuidance.model_validate(item) for item in list(payload.get("guidance") or [])],
        metric_history=[NewsroomMetricHistory.model_validate(item) for item in list(payload.get("metric_history") or [])],
        challenges=[str(item) for item in list(payload.get("challenges") or [])],
        watch_items=[str(item) for item in list(payload.get("watch_items") or [])],
        missing_items=[str(item) for item in list(payload.get("missing_items") or [])],
        management_language_mismatch=str(payload.get("management_language_mismatch") or ""),
        open_claims=[tuple(item) for item in list(payload.get("open_claims") or [])],  # type: ignore[list-item]
        evidence_texts=[str(item) for item in list(payload.get("evidence_texts") or [])],
        source_published_at={str(k): str(v) for k, v in dict(payload.get("source_published_at") or {}).items()},
        source_urls={str(k): str(v) for k, v in dict(payload.get("source_urls") or {}).items()},
    )


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    article = build_newsroom_article(_packet(case))
    expected = dict(case.get("expected") or {})
    errors: list[str] = []

    if article.copydesk_status != expected.get("copydesk_status", "pass"):
        errors.append(
            f"copydesk_status expected={expected.get('copydesk_status', 'pass')!r} actual={article.copydesk_status!r}"
        )
    headline_contains = str(expected.get("headline_contains") or "").strip()
    if headline_contains and headline_contains.lower() not in article.headline.lower():
        errors.append(f"headline missing {headline_contains!r}: {article.headline!r}")
    news_contains = str(expected.get("news_contains") or "").strip()
    if news_contains and news_contains.lower() not in article.news.text.lower():
        errors.append(f"news missing {news_contains!r}: {article.news.text!r}")
    context_contains = str(expected.get("context_contains") or "").strip()
    if context_contains and not any(context_contains.lower() in item.text.lower() for item in article.context):
        errors.append(f"context missing {context_contains!r}")
    expected_number_points = expected.get("number_points")
    if expected_number_points is not None:
        actual = len(article.the_number.points) if article.the_number is not None else 0
        if actual != int(expected_number_points):
            errors.append(f"number_points expected={expected_number_points} actual={actual}")
    if bool(expected.get("has_catch")) != (article.the_catch is not None):
        errors.append(f"has_catch expected={bool(expected.get('has_catch'))} actual={article.the_catch is not None}")
    if bool(expected.get("has_missing")) != bool(article.whats_missing):
        errors.append(f"has_missing expected={bool(expected.get('has_missing'))} actual={bool(article.whats_missing)}")
    if bool(expected.get("has_next_test")) != (article.next_test is not None):
        errors.append(f"has_next_test expected={bool(expected.get('has_next_test'))} actual={article.next_test is not None}")
    expected_flags = [str(item) for item in list(expected.get("flag_prefixes") or [])]
    for prefix in expected_flags:
        if not any(flag.startswith(prefix) for flag in article.copydesk_flags):
            errors.append(f"missing copydesk flag prefix {prefix!r}: {article.copydesk_flags!r}")

    return {
        "case_id": str(case.get("case_id") or "unknown"),
        "passed": not errors,
        "errors": errors,
        "actual": {
            "headline": article.headline,
            "news": article.news.text,
            "context": [item.text for item in article.context],
            "copydesk_status": article.copydesk_status,
            "copydesk_flags": article.copydesk_flags,
            "number_points": len(article.the_number.points) if article.the_number is not None else 0,
            "has_catch": article.the_catch is not None,
            "has_missing": bool(article.whats_missing),
            "has_next_test": article.next_test is not None,
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
    parser = argparse.ArgumentParser(description="Run the AIM Daily newsroom benchmark.")
    parser.add_argument("--cases", default="benchmarks/aim_daily_newsroom_cases.json")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = run_benchmark(Path(args.cases))
    print(
        "[aim-daily-newsroom] "
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
            f"[aim-daily-newsroom] {case['case_id']}: pass={case['passed']} "
            f"copydesk={case['actual']['copydesk_status']} headline={case['actual']['headline']!r}",
            flush=True,
        )
        for error in case["errors"]:
            print(f"[aim-daily-newsroom] ERROR {case['case_id']}: {error}", flush=True)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
