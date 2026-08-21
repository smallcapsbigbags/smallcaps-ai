from pathlib import Path

from analyst.gold_standard import (
    GoldStandardJudgement,
    benchmark_acceptance,
    headline_matches,
    load_real_benchmark_cases,
)


def _judgement(score_delta: int = 0) -> GoldStandardJudgement:
    return GoldStandardJudgement(
        factual_grounding=20,
        investor_relevance=10,
        comparator_discipline=12,
        useful_calculations=10,
        commercial_interpretation=10,
        sector_event_kpi=8,
        balance_sheet_capital_control=8,
        uncertainty_and_explanation=6,
        investment_case_change=6,
        repeatability_and_next_steps=5,
        plain_english=max(0, 5 - score_delta),
        main_change_identified=True,
        assessed_case_change="strengthens",
        impact_alignment="aligned",
    )


def test_real_benchmark_suite_has_20_unique_cases():
    cases = load_real_benchmark_cases(Path("benchmarks/real_cases.json"))
    assert len(cases) == 20
    assert len({case.id for case in cases}) == 20
    assert len({(case.day, case.ticker, case.id) for case in cases}) == 20


def test_gold_standard_rubric_weights_sum_to_100():
    judgement = _judgement()
    assert judgement.total_score == 100
    assert judgement.passed


def test_headline_matcher_accepts_any_case_token():
    case = load_real_benchmark_cases(Path("benchmarks/real_cases.json"))[0]
    assert headline_matches(case, "Share Buyback, Rule 9 Waiver and Notice of GM")
    assert not headline_matches(case, "Total Voting Rights")


def test_benchmark_acceptance_requires_human_grade_floor():
    strong = [_judgement() for _ in range(20)]
    report = benchmark_acceptance(strong)
    assert report["passed"]
    weak = strong.copy()
    weak[0] = _judgement(score_delta=5)
    # 95/100 still clears the floor; create a critical failure to force rejection.
    weak[0] = weak[0].model_copy(update={"critical_failures": ["invented number"]})
    report = benchmark_acceptance(weak)
    assert not report["passed"]


def test_rubric_document_contains_locked_human_behaviours():
    rubric = Path("benchmarks/GOLD_STANDARD_RUBRIC.md").read_text(encoding="utf-8")
    for token in (
        "versus what?",
        "Sector- and event-specific KPI selection",
        "Useful calculations and auditability",
        "Is it repeatable?",
        "Impact and market reaction remain analytically separate",
        "reported facts, Smallcaps.ai calculations and Smallcaps.ai interpretation",
    ):
        assert token in rubric
