from __future__ import annotations

import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo

from analyst.analyzer import OpenAIAnalystEngine
from database.db import create_database_engine, create_session_factory, init_database
from database.operations import OperationsRepository, advisory_job_lock
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import InvestegateDailyAIMSource
from pipeline import FoundationPipeline
from settings import Settings

LONDON = ZoneInfo("Europe/London")
JOB_NAME = "daily-aim-ingestion"


def main(day: date | None = None) -> None:
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
        with advisory_job_lock(engine, JOB_NAME) as acquired:
            run_id = operations.begin_job(JOB_NAME, run_key=datetime.now(LONDON).date().isoformat())
            if not acquired:
                operations.finish_job(run_id, status="skipped", warnings=["Another ingestion worker currently holds the advisory lock."])
                print("Daily AIM ingestion skipped: another worker is active")
                return
            try:
                analyst = OpenAIAnalystEngine(api_key=settings.openai_api_key, model=settings.openai_model, max_output_tokens=settings.openai_max_output_tokens)
                pipeline = FoundationPipeline(repository=repository, analyst_engine=analyst, prompt_version=settings.prompt_version, min_evidence_chars=settings.min_evidence_chars)
                source = InvestegateDailyAIMSource(api_key=settings.openai_api_key, deep_model=settings.openai_deep_model, deep_batch_size=settings.deep_search_batch_size, max_document_chars=settings.max_document_chars, max_pages=settings.investegate_aim_max_pages)
                service = DailyAIMIngestionService(source=source, repository=repository, pipeline=pipeline, max_ai_items=settings.max_ai_items)
                result = service.run(day=day)
                summary = {"discovered": result.discovered, "known": result.already_known, "analysed": result.analysed, "review": result.review_required, "routine": result.routine_persisted, "deferred": result.deferred, "blocked": result.blocked, "failed": result.failed}
                degraded = any((result.review_required, result.deferred, result.blocked, result.failed))
                operations.finish_job(run_id, status="degraded" if degraded else "success", summary=summary, warnings=[*warnings, *result.warnings])
            except Exception as exc:
                operations.finish_job(run_id, status="failed", warnings=warnings, error_text=f"{type(exc).__name__}: {exc}")
                raise
        print("Daily AIM ingestion:", " ".join(f"{key}={value}" for key, value in summary.items()))
        for warning in result.warnings:
            print("WARNING:", warning)
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily AIM ingestion job.")
    parser.add_argument(
        "--date",
        dest="date",
        type=str,
        default=None,
        help="Date to ingest announcements for, in YYYY-MM-DD format. Defaults to today.",
    )
    args = parser.parse_args()
    target_day = date.fromisoformat(args.date) if args.date else None
    main(day=target_day)
