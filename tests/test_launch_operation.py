from __future__ import annotations

import json
from pathlib import Path


def _railway_config(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_all_production_services_run_integrity_audit_before_deploy() -> None:
    for path, service in (
        ("railway.json", "web"),
        ("railway.ingest.json", "ingestion"),
        ("railway.prices.json", "prices"),
    ):
        config = _railway_config(path)
        commands = list(config["deploy"]["preDeployCommand"])
        assert any(
            f"jobs.validate_runtime --service {service}" in command
            for command in commands
        )
        assert any(
            f"jobs.audit_production --service {service}" in command
            and "--record" in command
            and "--reconcile-stale" in command
            and "--historical-worker-failures-warn" in command
            for command in commands
        )


def test_ingestion_cron_also_runs_market_reactions_for_mvp() -> None:
    ingestion_job = Path("jobs/ingest_daily.py").read_text(encoding="utf-8")
    price_job = Path("jobs/update_prices.py").read_text(encoding="utf-8")
    config = _railway_config("railway.ingest.json")

    assert "run_price_job" in ingestion_job
    assert "if settings.market_data_enabled" in ingestion_job
    assert "def _price_summary" in ingestion_job
    assert '"price_status": outcome.status' in ingestion_job
    assert "_price_summary(price_outcome)" in ingestion_job
    assert 'JOB_NAME = "daily-price-reactions"' in price_job
    assert "advisory_job_lock(active_engine, JOB_NAME)" in price_job
    assert config["deploy"]["cronSchedule"] == "*/10 6-18 * * 1-5"


def test_production_audit_does_not_require_openai_or_market_requests() -> None:
    audit = Path("database/production_audit.py").read_text(encoding="utf-8")
    assert "from openai" not in audit
    assert "requests." not in audit
    assert "YahooPriceClient" not in audit
    assert "DATABASE_WRITE_ROUNDTRIP" in audit
    assert "PUBLIC_SOURCE_LINKS" in audit
    assert "NO_STUCK_JOBS" in audit
