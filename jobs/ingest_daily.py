from __future__ import annotations

from analyst.analyzer import OpenAIAnalystEngine
from database.db import create_database_engine, create_session_factory, init_database
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import InvestegateDailyAIMSource
from pipeline import FoundationPipeline
from settings import Settings


def main() -> None:
    settings = Settings.from_env()
    engine = create_database_engine(settings.database_url)
    init_database(engine)
    repository = IntelligenceRepository(create_session_factory(engine))

    analyst = OpenAIAnalystEngine(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=analyst,
        prompt_version=settings.prompt_version,
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
    )
    result = service.run()
    print(
        "Daily AIM ingestion:",
        f"discovered={result.discovered}",
        f"known={result.already_known}",
        f"analysed={result.analysed}",
        f"routine={result.routine_persisted}",
        f"deferred={result.deferred}",
        f"failed={result.failed}",
    )
    for warning in result.warnings:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()
