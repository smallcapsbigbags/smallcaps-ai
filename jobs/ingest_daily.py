from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from analyst.analyzer import OpenAIAnalystEngine
from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import InvestegateDailyAIMSource
from jobs.update_prices import PriceJobOutcome, run_price_job
from pipeline import FoundationPipeline
from settings import Settings

LONDON = ZoneInfo("Europe/London")
JOB_NAME = "daily-aim-ingestion"


def _progress(message: str) -> None:
    print(f"[ingestion] {message}", flush=True)


def _price_warnings(outcome: PriceJobOutcome | None) -> list[str]:
    if outcome is None:
        return []
    output = [f"Market reactions: {warning}" for warning in outcome.warnings]
    if outcome.error_text:
        output.append(f"Market reactions failed: {outcome.error_text}")
    return output


def main() -> None:
    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("ingestion")
    if errors:
        raise RuntimeError(" | ".join(errors))
    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        repository = IntelligenceRepository(factory)
        operations = OperationsRepository(factory)
        operations.reconcile_stale_running(job_name=JOB_NAME)
        price_outcome: PriceJobOutcome | None = None
        combined_warnings: list[str] = list(warnings)

        with advisory_job_lock(engine, JOB_NAME) as acquired:
            run_id = operations.begin_job(
                JOB_NAME,
                run_key=datetime.now(LONDON).date().isoformat(),
            )
            if not acquired:
                operations.finish_job(
                    run_id,
                    status="skipped",
                    warnings=[
                        "Another ingestion worker currently holds the advisory lock."
                    ],
                )
                print(
                    "Daily AIM ingestion skipped: another worker is active",
                    flush=True,
                )
                return
            try:
                analyst = OpenAIAnalystEngine(
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    max_output_tokens=settings.openai_max_output_tokens,
                )
                pipeline = FoundationPipeline(
                    repository=repository,
                    analyst_engine=analyst,
                    prompt_version=settings.prompt_version,
                    min_evidence_chars=settings.min_evidence_chars,
                )
                source = InvestegateDailyAIMSource(
                    api_key=settings.openai_api_key,
                    deep_model=settings.openai_deep_model,
                    deep_batch_size=settings.deep_search_batch_size,
                    max_document_chars=settings.max_document_chars,
                    max_pages=settings.investegate_aim_max_pages,
                )
                service = DailyAIMIngestionService(
                    source=source,
                    repository=repository,
                    pipeline=pipeline,
                    max_ai_items=settings.max_ai_items,
                    progress=_progress,
                )
                result = service.run()
                summary: dict[str, object] = {
                    "discovered": result.discovered,
                    "known": result.already_known,
                    "analysed": result.analysed,
                    "review": result.review_required,
                    "routine": result.routine_persisted,
                    "deferred": result.deferred,
                    "blocked": result.blocked,
                    "failed": result.failed,
                }
                combined_warnings.extend(result.warnings)

                # The AIM cron already runs throughout the LSE day. Reusing that
                # reliable service for market reactions makes price context work in
                # the MVP even before a separate Railway price cron is provisioned.
                # A dedicated price worker remains safe because its separate
                # advisory lock makes overlapping cycles skip rather than duplicate.
                if settings.market_data_enabled:
                    _progress("Updating event-day market reactions")
                    price_outcome = run_price_job(
                        settings,
                        engine=engine,
                        raise_on_failure=False,
                    )
                    summary["price_status"] = price_outcome.status
                    for key, value in price_outcome.summary.items():
                        summary[f"price_{key}"] = value
                    combined_warnings.extend(_price_warnings(price_outcome))

                degraded = any(
                    (
                        result.review_required,
                        result.deferred,
                        result.blocked,
                        result.failed,
                        price_outcome is not None
                        and price_outcome.status == "failed",
                    )
                )
                operations.finish_job(
                    run_id,
                    status="degraded" if degraded else "success",
                    summary=summary,
                    warnings=combined_warnings,
                )
            except Exception as exc:
                operations.finish_job(
                    run_id,
                    status="failed",
                    warnings=combined_warnings,
                    error_text=f"{type(exc).__name__}: {exc}",
                )
                raise

        print(
            "Daily AIM ingestion:",
            " ".join(f"{key}={value}" for key, value in summary.items()),
            flush=True,
        )
        for warning in combined_warnings:
            print("WARNING:", warning, flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
