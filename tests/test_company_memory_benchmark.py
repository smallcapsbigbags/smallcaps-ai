from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from analyst.company_memory import build_company_memory
from analyst.company_memory_evaluation import (
    CompanyMemoryJudgement,
    company_memory_acceptance,
    deterministic_case_checks,
    load_company_memory_cases,
)
from analyst.models import AnalystNote, KeyFact, WhatChanged


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


def _benchmark_note(
    source_id: str,
    *,
    colour: str,
    score: int,
    comparator_source_id: str,
) -> AnalystNote:
    return AnalystNote(
        source_id=source_id,
        rns_type="Results & trading",
        impact_colour=colour,
        impact_score=score,
        impact_level="medium" if score <= 3 else "high",
        impact_rationale="Today's change is material in the disclosed context.",
        headline="Main change identified",
        takeaway="The note leads with today's main event and uses earlier evidence.",
        key_facts=[
            KeyFact(
                label="Historic comparator",
                metric="historic comparator",
                value="Current value",
                basis="reported",
                comparator="Previous value",
                comparator_type="prior-disclosure",
                comparator_source_id=comparator_source_id,
                previous_value="Previous value",
            )
        ],
        what_changed=WhatChanged(
            before="The previous position was disclosed earlier.",
            today="The current position has changed.",
            read_through="The difference changes the investment evidence.",
            coverage_status="building",
        ),
        analyst_view="Today's evidence strengthens the investment case.",
        confidence=0.9,
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
        history_ids = {
            str(record.get("source_id") or "") for record in case.history
        }
        assert set(case.required_prior_source_ids).issubset(history_ids)
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


def test_deterministic_case_checks_require_allowed_impact_and_prior_source() -> None:
    case = load_company_memory_cases(
        Path("benchmarks/company_memory_cases.json")
    )[0]
    note = _benchmark_note(
        case.current_announcement.source_id,
        colour="amber",
        score=3,
        comparator_source_id=case.required_prior_source_ids[0],
    )

    report = deterministic_case_checks(case, note)

    assert report["passed"]
    assert report["errors"] == []


def test_deterministic_case_checks_reject_wrong_colour_and_missing_source() -> None:
    case = load_company_memory_cases(
        Path("benchmarks/company_memory_cases.json")
    )[0]
    note = _benchmark_note(
        case.current_announcement.source_id,
        colour="red",
        score=5,
        comparator_source_id="unrelated-source",
    )

    report = deterministic_case_checks(case, note)

    assert not report["passed"]
    assert any("impact colour" in error for error in report["errors"])
    assert any("required prior source IDs" in error for error in report["errors"])
