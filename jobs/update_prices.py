from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock
from database.product import ProductRepository
from market.pricing import YahooPriceClient
from market.reactions import DailyPriceReactionService
from settings import Settings

LONDON = ZoneInfo("Europe/London")
JOB_NAME = "daily-price-reactions"


def main() -> None:
    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("prices")
    if errors:
        raise RuntimeError(" | ".join(errors))
    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        repository = ProductRepository(factory)
        operations = OperationsRepository(factory)
        with advisory_job_lock(engine, JOB_NAME) as acquired:
            run_id = operations.begin_job(JOB_NAME, run_key=datetime.now(LONDON).date().isoformat())
            if not acquired:
                operations.finish_job(run_id, status="skipped", warnings=["Another price worker currently holds the advisory lock."])
                print("Market reaction update skipped: another worker is active")
                return
            try:
                service = DailyPriceReactionService(repository=repository, client=YahooPriceClient(timeout_seconds=settings.market_data_timeout_seconds))
                result = service.run()
                summary = {"targets": result.target_count, "tickers": result.ticker_count, "updated": result.updated, "pending": result.pending, "stale": result.stale, "failed": result.failed}
                operations.finish_job(run_id, status="degraded" if result.stale or result.failed else "success", summary=summary, warnings=[*warnings, *result.warnings])
            except Exception as exc:
                operations.finish_job(run_id, status="failed", warnings=warnings, error_text=f"{type(exc).__name__}: {exc}")
                raise
        print("Daily market reaction:", " ".join(f"{key}={value}" for key, value in summary.items()))
        for warning in result.warnings:
            print("WARNING:", warning)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
