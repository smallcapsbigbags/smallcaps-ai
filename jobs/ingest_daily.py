from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from analyst.analyzer import OpenAIAnalystEngine
from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.licensed_daily import LicensedDailyAIMSource
from ingestion.source_wrapper import ProvenanceNormalisingDailySource
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
    *,
    source_mode: str,
) -> dict[str, object]:
    return {
        "source_mode": source_mode,
        "source_name": "",
        "source_fca_nsm": 0,
        "source_official_rns": 0,
        "source_non_mirror": 0,
        "source_mirror_only": 0,
        "source_missing": 0,
        "discovered": 0,
        "known": 0,
        "analysed": 0,
        "review": 0,
        "routine": 0,
        "archived": 0,
        "light": 0,
        "escalated": 0,
        "analyst_calls_avoided": 0,
        "analyst_initial_calls": 0,
        "analyst_review_calls": 0,
        "analyst_reviews_avoided": 0,
        "analyst_model_calls": 0,
        "deferred": 0,
        "blocked": 0,
        "failed": 0,
        # Retained as a compatibility field. The retired AIM Daily sync no longer runs.
        "story_links_created": 0,
        **_price_summary(price_outcome),
    }


def _build_source(
    settings: Settings,
    repository: IntelligenceRepository,
) -> Any:
    common = {
        "repository": repository,
        "api_key": settings.openai_api_key,
        "deep_model": settings.openai_deep_model,
        "deep_batch_size": settings.deep_search_batch_size,
        "max_document_chars": settings.max_document_chars,
        "max_pages": settings.investegate_aim_max_pages,
    }
    mode = settings.aim_source_policy().normalised_mode
    if mode == "licensed":
        return LicensedDailyAIMSource(
            feed_url=settings.aim_licensed_feed_url,
            feed_token=settings.aim_licensed_feed_token,
            feed_timeout_seconds=settings.aim_licensed_feed_timeout_seconds,
            **common,
        )
    if mode == "owner-test":
        return VerifiedFallbackDailyAIMSource(**common)
    raise RuntimeError(f"AIM discovery source is not enabled: mode={mode!r}")


def main() -> None:
    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("ingestion")
    if errors:
        raise RuntimeError(" | ".join(errors))

    source_policy = settings.aim_source_policy()
    source_mode = source_policy.normalised_mode
    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        repository = IntelligenceRepository(factory)
        operations = OperationsRepository(factory)
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
                    summary=_empty_ingestion_summary(
                        price_outcome,
                        source_mode=source_mode,
                    ),
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
                summary={
                    "source_mode": source_mode,
                    **_price_summary(price_outcome),
                },
            )

            if source_mode == "disabled":
                disabled_warning = (
                    "AIM discovery is disabled by policy. Existing company "
                    "repositories and market-reaction maintenance remain available."
                )
                combined_warnings.append(disabled_warning)
                summary = _empty_ingestion_summary(
                    price_outcome,
                    source_mode=source_mode,
                )
                operations.finish_job(
                    run_id,
                    status="skipped",
                    summary=summary,
                    warnings=combined_warnings,
                )
                print(
                    "Daily AIM ingestion skipped: AIM_DISCOVERY_MODE=disabled",
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
                raw_source = _build_source(settings, repository)
                source = ProvenanceNormalisingDailySource(raw_source)
                service = DailyAIMIngestionService(
                    source=source,
                    repository=repository,
                    pipeline=pipeline,
                    max_ai_items=settings.max_ai_items,
                    progress=_progress,
                )
                result = service.run()
                analyst_stats = analyst.model_call_stats()
                provenance = source.provenance_counts()
                if provenance.get("mirror_only", 0):
                    combined_warnings.append(
                        "Source provenance retained "
                        f"{provenance['mirror_only']} mirror-only catalogue "
                        "record(s); these are not treated as FCA/official verification."
                    )

                summary: dict[str, object] = {
                    "source_mode": source_mode,
                    "source_name": str(getattr(raw_source, "name", "")),
                    **{
                        f"source_{key}": value
                        for key, value in provenance.items()
                    },
                    "discovered": result.discovered,
                    "known": result.already_known,
                    "analysed": result.analysed,
                    "review": result.review_required,
                    "routine": result.routine_persisted,
                    "archived": result.archived,
                    "light": result.light_processed,
                    "escalated": result.escalated_to_full,
                    "analyst_calls_avoided": result.analyst_calls_avoided,
                    "analyst_initial_calls": analyst_stats["initial_calls"],
                    "analyst_review_calls": analyst_stats["review_calls"],
                    "analyst_reviews_avoided": analyst_stats["reviews_avoided"],
                    "analyst_model_calls": analyst_stats["total_calls"],
                    "deferred": result.deferred,
                    "blocked": result.blocked,
                    "failed": result.failed,
                    # The customer-facing AIM Daily was retired in Pass 1.
                    "story_links_created": 0,
                    **_price_summary(price_outcome),
                }
                combined_warnings.extend(result.warnings)
                degraded = any(
                    (
                        result.review_required,
                        result.deferred,
                        result.blocked,
                        result.failed,
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
                    summary={
                        "source_mode": source_mode,
                        **_price_summary(price_outcome),
                    },
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
