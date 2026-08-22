from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Engine

from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock
from database.product import ProductRepository
from market.pricing import YahooPriceClient
from market.reactions import DailyPriceReactionService, PriceClient
from settings import Settings

LONDON = ZoneInfo("Europe/London")
JOB_NAME = "daily-price-reactions"
PriceJobStatus = Literal["success", "degraded", "failed", "skipped"]


@dataclass(frozen=True)
class PriceJobOutcome:
    status: PriceJobStatus
    summary: dict[str, int]
    warnings: tuple[str, ...] = ()
    error_text: str = ""

    @property
    def completed(self) -> bool:
        return self.status in {"success", "degraded"}


def _empty_summary() -> dict[str, int]:
    return {
        "targets": 0,
        "tickers": 0,
        "updated": 0,
        "pending": 0,
        "stale": 0,
        "failed": 0,
    }


def run_price_job(
    settings: Settings,
    *,
    engine: Engine | None = None,
    client: PriceClient | None = None,
    now_london: datetime | None = None,
    raise_on_failure: bool = False,
) -> PriceJobOutcome:
    """Run one price-reaction cycle with its own lock and persisted job record.

    The ingestion worker calls this after each RNS cycle, so market reactions remain
    operational even when a separate Railway price service has not yet been created.
    A dedicated price service may still call the same function; the advisory lock
    prevents duplicate work.
    """

    errors, runtime_warnings = settings.runtime_issues("prices")
    if errors:
        error_text = " | ".join(errors)
        if raise_on_failure:
            raise RuntimeError(error_text)
        return PriceJobOutcome(
            status="failed",
            summary=_empty_summary(),
            warnings=tuple(runtime_warnings),
            error_text=error_text,
        )

    owns_engine = engine is None
    active_engine = engine or create_database_engine(settings.database_url)
    try:
        init_database(active_engine)
        factory = create_session_factory(active_engine)
        repository = ProductRepository(factory)
        operations = OperationsRepository(factory)
        run_day = (now_london or datetime.now(LONDON)).astimezone(LONDON).date()

        with advisory_job_lock(active_engine, JOB_NAME) as acquired:
            run_id = operations.begin_job(JOB_NAME, run_key=run_day.isoformat())
            if not acquired:
                message = "Another price worker currently holds the advisory lock."
                operations.finish_job(
                    run_id,
                    status="skipped",
                    summary=_empty_summary(),
                    warnings=[*runtime_warnings, message],
                )
                return PriceJobOutcome(
                    status="skipped",
                    summary=_empty_summary(),
                    warnings=tuple([*runtime_warnings, message]),
                )

            try:
                service = DailyPriceReactionService(
                    repository=repository,
                    client=client
                    or YahooPriceClient(
                        timeout_seconds=settings.market_data_timeout_seconds
                    ),
                )
                result = service.run(now_london=now_london)
                summary = {
                    "targets": result.target_count,
                    "tickers": result.ticker_count,
                    "updated": result.updated,
                    "pending": result.pending,
                    "stale": result.stale,
                    "failed": result.failed,
                }
                status: PriceJobStatus = (
                    "degraded" if result.stale or result.failed else "success"
                )
                all_warnings = [*runtime_warnings, *result.warnings]
                operations.finish_job(
                    run_id,
                    status=status,
                    summary=summary,
                    warnings=all_warnings,
                )
                return PriceJobOutcome(
                    status=status,
                    summary=summary,
                    warnings=tuple(all_warnings),
                )
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"[:4000]
                operations.finish_job(
                    run_id,
                    status="failed",
                    summary=_empty_summary(),
                    warnings=runtime_warnings,
                    error_text=error_text,
                )
                if raise_on_failure:
                    raise
                return PriceJobOutcome(
                    status="failed",
                    summary=_empty_summary(),
                    warnings=tuple(runtime_warnings),
                    error_text=error_text,
                )
    finally:
        if owns_engine:
            active_engine.dispose()


def main() -> None:
    settings = Settings.from_env()
    outcome = run_price_job(settings, raise_on_failure=True)
    print(
        "Daily market reaction:",
        f"status={outcome.status}",
        " ".join(f"{key}={value}" for key, value in outcome.summary.items()),
        flush=True,
    )
    for warning in outcome.warnings:
        print("WARNING:", warning, flush=True)


if __name__ == "__main__":
    main()
