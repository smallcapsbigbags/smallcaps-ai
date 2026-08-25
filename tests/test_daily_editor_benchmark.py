from pathlib import Path

from jobs.run_daily_editor_benchmark import run_benchmark


def test_historical_aim_daily_editor_benchmark_passes() -> None:
    report = run_benchmark(Path("benchmarks/aim_daily_editor_cases.json"))

    assert report["passed"] is True, report
    assert report["case_count"] == 4
    assert report["passed_cases"] == 4
    assert report["failed_cases"] == []
