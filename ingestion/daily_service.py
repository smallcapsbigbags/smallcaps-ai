from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from database.queries import known_source_ids
from database.repository import IntelligenceRepository
from ingestion.investegate_daily import InvestegateDailyAIMSource
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")


@dataclass
class DailyIngestionResult:
    day: date
    discovered: int = 0
    already_known: int = 0
    analysed: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    processed_source_ids: list[str] = field(default_factory=list)
    failed_source_ids: list[str] = field(default_factory=list)


class DailyAIMIngestionService:
    """Current Daily AIM flow: Investegate discovery → OpenAI evidence → analysis.

    PostgreSQL replaces the old JSON cache as the deduplication and persistence layer.
    Manual ingestion remains available separately for testing and recovery.
    """

    def __init__(
        self,
        *,
        source: InvestegateDailyAIMSource,
        repository: IntelligenceRepository,
        pipeline: FoundationPipeline,
    ) -> None:
        self.source = source
        self.repository = repository
        self.pipeline = pipeline

    def run(self, day: date | None = None) -> DailyIngestionResult:
        day = day or datetime.now(LONDON).date()
        catalogue, source_warnings = self.source.list_announcements(day)
        known = known_source_ids(
            self.repository, [item.source_id for item in catalogue]
        )
        pending = [item for item in catalogue if item.source_id not in known]

        result = DailyIngestionResult(
            day=day,
            discovered=len(catalogue),
            already_known=len(known),
            warnings=list(source_warnings),
        )

        if not pending:
            return result

        result.warnings.extend(self.source.prepare_documents(pending))

        for item in pending:
            announcement = self.source.fetch_document(item)
            try:
                persisted = self.pipeline.process(announcement)
            except Exception as exc:
                result.failed += 1
                result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"{item.ticker} {item.source_id}: analysis failed: {type(exc).__name__}: {exc}"[:700]
                )
                continue

            result.analysed += 1
            result.processed_source_ids.append(persisted.source_id)

        return result
