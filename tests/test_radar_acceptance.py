from jobs.radar_acceptance import run_radar_acceptance


def test_radar_acceptance_creates_schema_and_passes_benchmark() -> None:
    report = run_radar_acceptance(
        "sqlite+pysqlite:///:memory:",
        allow_sqlite=True,
        benchmark_path="benchmarks/radar_cases.json",
    )
    assert report["passed"] is True
    assert report["failure_count"] == 0
    checks = {item["code"]: item for item in report["checks"]}
    assert checks["RADAR_SCHEMA"]["status"] == "pass"
    assert checks["RADAR_BENCHMARK"]["status"] == "pass"
    assert checks["RADAR_BENCHMARK"]["details"]["passed_cases"] == 8
