from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from analyst.classification import is_administrative_routine, material_priority
from analyst.models import AnnouncementInput
from analyst.routine import routine_note
from database.queries import known_source_ids
from database.repository import IntelligenceRepository
from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")


@dataclass
class DailyIngestionResult:
    day: date
    discovered: int = 0
    already_known: int = 0
    analysed: int = 0
    routine_persisted: int = 0
    deferred: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    processed_source_ids: list[str] = field(default_factory=list)
    failed_source_ids: list[str] = field(default_factory=list)


class DailyAIMIngestionService:
    """Current Daily AIM flow: Investegate discovery → OpenAI evidence → analysis.

    This mirrors the working RNS-Xray behaviour:
    - discover all AIM catalogue rows;
    - persist true administrative routine records without deep AI calls;
    - prioritise investment-relevant rows for evidence retrieval/analysis;
    - leave deferred/failed material rows eligible for a later retry;
    - use PostgreSQL instead of daily JSON files for dedupe and persistence.
    """

    def __init__(
        self,
        *,
        source: InvestegateDailyAIMSource,
        repository: IntelligenceRepository,
        pipeline: FoundationPipeline,
        max_ai_items: int = 36,
    ) -> None:
        self.source = source
        self.repository = repository
        self.pipeline = pipeline
        self.max_ai_items = max(3, max_ai_items)

    def _metadata_input(
        self, item: CatalogueAnnouncement, *, reason: str
    ) -> AnnouncementInput:
        return AnnouncementInput(
            source_id=item.source_id,
            ticker=item.ticker,
            company=item.company,
            published_at=item.published_at,
            title=item.title,
            text=f"Regulatory announcement catalogue record: {item.title}.\n\nSOURCE NOTE: {reason}",
            source_url=item.source_url,
            categories=item.categories,
        )

    def _persist_routine(self, item: CatalogueAnnouncement) -> None:
        reason = (
            "Routine administrative disclosure classified deterministically; "
            "current RNS-Xray behaviour does not spend a deep AI call on this item."
        )
        announcement = self._metadata_input(item, reason=reason)
        note = routine_note(announcement, reason=reason)
        self.repository.save_analysis(
            announcement,
            note,
            prompt_version=self.pipeline.prompt_version,
            model_version="deterministic-metadata",
        )

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

        routine = [item for item in pending if is_administrative_routine(item)]
        relevant = [item for item in pending if not is_administrative_routine(item)]
        selected = sorted(
            relevant,
            key=lambda item: (material_priority(item), item.published_at),
            reverse=True,
        )[: self.max_ai_items]
        result.deferred = max(0, len(relevant) - len(selected))
        if result.deferred:
            result.warnings.append(
                f"{result.deferred} investment-relevant announcement(s) deferred by MAX_AI_ITEMS={self.max_ai_items}; they remain unpersisted and eligible for the next run."
            )

        for item in routine:
            try:
                self._persist_routine(item)
                result.routine_persisted += 1
                result.processed_source_ids.append(item.source_id)
            except Exception as exc:
                result.failed += 1
                result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"{item.ticker} {item.source_id}: routine persistence failed: {type(exc).__name__}: {exc}"[:700]
                )

        if not selected:
            return result

        result.warnings.extend(self.source.prepare_documents(selected))

        for item in selected:
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
