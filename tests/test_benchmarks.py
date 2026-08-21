from pathlib import Path

from analyst.evaluation import evaluate_benchmark, load_benchmark_cases
from analyst.models import AnalystNote, WhatChanged


def test_canonical_benchmark_suite_is_complete_and_unique():
    cases = load_benchmark_cases(Path("benchmarks/cases.json"))
    assert len(cases) == 16
    assert len({case.id for case in cases}) == len(cases)
    assert all(
        case.expectation.min_score <= case.expectation.max_score
        for case in cases
    )


def test_benchmark_evaluator_checks_colour_score_and_concepts():
    case = load_benchmark_cases(Path("benchmarks/cases.json"))[0]
    note = AnalystNote(
        source_id="benchmark-profit-warning-cash",
        rns_type="Results & trading",
        impact_colour="red",
        impact_score=5,
        impact_level="critical",
        headline="EBITDA guidance cut as cash falls",
        takeaway="The company cut EBITDA guidance and net cash fell materially.",
        what_changed=WhatChanged(
            before="EBITDA guidance was £10m to £12m.",
            today="Guidance is now £6m to £7m and net cash is £2m.",
            read_through="The earnings and liquidity position both deteriorated.",
        ),
        analyst_view="The guidance cut and cash decline are the key issues.",
    )
    result = evaluate_benchmark(case, note)
    assert result.passed
