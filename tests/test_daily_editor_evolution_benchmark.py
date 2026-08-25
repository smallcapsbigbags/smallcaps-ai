from pathlib import Path

from jobs.run_daily_editor_evolution_benchmark import run_benchmark


def test_aim_daily_edition_evolution_benchmark_passes() -> None:
    report = run_benchmark(Path("benchmarks/aim_daily_editor_evolution_cases.json"))

    assert report["passed"] is True, report
    assert report["case_count"] == 2
    assert report["passed_cases"] == 2
    assert report["failed_cases"] == []
