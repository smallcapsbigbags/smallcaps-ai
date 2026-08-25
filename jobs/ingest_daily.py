from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from analyst.analyzer import OpenAIAnalystEngine
from database.db import create_database_engine, create_session_factory, init_database
from database.editorial_calibration import EditorialCalibrationRepository
from database.operations import OperationsRepository, advisory_job_lock
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.verified_fallback_daily import VerifiedFallbackDailyAIMSource
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


def _price_summary(outcome: PriceJobOutcome | None) -> dict[str, object]:
    if outcome is None:
        return {}
    return {
        "price_status": outcome.status,
        **{f"price_{key}": value for key, value in outcome.summary.items()},
    }


def _empty_ingestion_summary(
    price_outcome: PriceJobOutcome | None,
) -> dict[str, object]:
    return {
        "discovered": 0,
        "known": 0,
        "analysed": 0,
        "review": 0,
        "routine": 0,
        "archived": 0,
        "light": 0,
        "escalated": 0,
        "analyst_calls_avoided": 0,
        "deferred": 0,
        "blocked": 0,
        "failed": 0,
        "story_links_created": 0,
        **_price_summary(price_outcome),
    }


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
        editorial = EditorialCalibrationRepository(factory)
        combined_warnings: list[str] = list(warnings)
        price_outcome: PriceJobOutcome | None = None

        if settings.market_data_enabled:
            _progress("Updating event-day market reactions")
            price_outcome = run_price_job(
                settings,
                engine=engine,
                raise_on_failure=False,
            )
            combined_warnings.extend(_price_warnings(price_outcome))

        with advisory_job_lock(engine, JOB_NAME) as acquired:
            if not acquired:
                run_id = operations.begin_job(
                    JOB_NAME,
                    run_key=datetime.now(LONDON).date().isoformat(),
                    summary=_price_summary(price_outcome),
                )
                lock_warning = (
                    "Another ingestion worker currently holds the advisory lock."
                )
                combined_warnings.append(lock_warning)
                operations.finish_job(
                    run_id,
                    status="skipped",
                    summary=_empty_ingestion_summary(price_outcome),
                    warnings=combined_warnings,
                )
                print(
                    "Daily AIM ingestion skipped: another worker is active",
                    flush=True,
                )
                return

            operations.reconcile_stale_running(job_name=JOB_NAME)
            run_id = operations.begin_job(
                JOB_NAME,
                run_key=datetime.now(LONDON).date().isoformat(),
                summary=_price_summary(price_outcome),
            )
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
                source = VerifiedFallbackDailyAIMSource(
                    repository=repository,
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
                story_links_created = 0
                story_sync_failed = False
                try:
                    story_links_created = editorial.ensure_story_links(
                        datetime.now(LONDON).date()
                    )
                except Exception as exc:
                    story_sync_failed = True
                    combined_warnings.append(
                        "AIM Daily developing-story sync failed: "
                        f"{type(exc).__name__}: {exc}"
                    )

                summary: dict[str, object] = {
                    "discovered": result.discovered,
                    "known": result.already_known,
                    "analysed": result.analysed,
                    "review": result.review_required,
                    "routine": result.routine_persisted,
                    "archived": result.archived,
                    "light": result.light_processed,
                    "escalated": result.escalated_to_full,
                    "analyst_calls_avoided": result.analyst_calls_avoided,
                    "deferred": result.deferred,
                    "blocked": result.blocked,
                    "failed": result.failed,
                    "story_links_created": story_links_created,
                    **_price_summary(price_outcome),
                }
                combined_warnings.extend(result.warnings)
                degraded = any(
                    (
                        result.review_required,
                        result.deferred,
                        result.blocked,
                        result.failed,
                        story_sync_failed,
                        price_outcome is not None
                        and price_outcome.status in {"degraded", "failed"},
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
                    summary=_price_summary(price_outcome),
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
