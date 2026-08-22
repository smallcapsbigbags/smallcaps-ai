from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from analyst.company_memory import build_company_memory
from analyst.company_memory_evaluation import (
    CompanyMemoryJudgement,
    company_memory_acceptance,
    load_company_memory_cases,
)


def _judgement(*, score_delta: int = 0) -> CompanyMemoryJudgement:
    return CompanyMemoryJudgement(
        current_event_priority=20,
        historical_comparison=20,
        point_in_time_provenance=15,
        guidance_and_claims=15,
        calculations_and_kpis=max(0, 15 - score_delta),
        impact_and_case_change=10,
        plain_english=5,
        main_change_identified=True,
        prior_context_used_safely=True,
        required_prior_sources_used=True,
        assessed_case_change="strengthens",
        impact_aligned=True,
    )


def test_company_memory_benchmark_cases_are_locked_and_point_in_time() -> None:
    cases = load_company_memory_cases(
        Path("benchmarks/company_memory_cases.json")
    )

    assert len(cases) == 4
    assert len({case.id for case in cases}) == 4
    assert {case.ticker for case in cases} == {"SPR", "AMCO", "GATC", "XYZ"}
    for case in cases:
        assert case.history
        current_at = case.current_announcement.published_at
        history_dates = [
            datetime.fromisoformat(
                str(record.get("published_at") or "").replace("Z", "+00:00")
            )
            for record in case.history
        ]
        assert all(published_at < current_at for published_at in history_dates)
        snapshot = build_company_memory(
            case.history,
            ticker=case.ticker,
            company=case.company,
            before=current_at,
        )
        assert snapshot.generated_before == current_at.astimezone(timezone.utc).isoformat()
        assert snapshot.announcement_count == len(case.history)
        assert case.required_prior_source_ids


def test_company_memory_judgement_weights_sum_to_100() -> None:
    judgement = _judgement()

    assert judgement.total_score == 100
    assert judgement.passed


def test_company_memory_acceptance_requires_every_case_to_pass() -> None:
    strong = [_judgement() for _ in range(4)]
    report = company_memory_acceptance(strong)
    assert report["passed"]

    weak = strong.copy()
    weak[0] = weak[0].model_copy(
        update={"critical_failures": ["future information used"]}
    )
    report = company_memory_acceptance(weak)
    assert not report["passed"]


def test_company_memory_acceptance_requires_safe_prior_context() -> None:
    results = [_judgement() for _ in range(4)]
    results[0] = results[0].model_copy(
        update={"prior_context_used_safely": False}
    )

    report = company_memory_acceptance(results)

    assert not report["passed"]
