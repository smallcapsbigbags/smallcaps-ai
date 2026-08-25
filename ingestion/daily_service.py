from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from analyst.evidence import EvidenceUnavailableError
from analyst.models import AnnouncementInput
from analyst.routine import routine_note
from database.queries import known_source_ids
from database.repository import IntelligenceRepository
from database.triage import TriageRepository
from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource
from ingestion.triage import TriageContext, TriageDecision, assess_light, initial_triage
from pipeline import AnalysisBlockedError, FoundationPipeline

LONDON = ZoneInfo("Europe/London")


@dataclass
class DailyIngestionResult:
    day: date
    discovered: int = 0
    already_known: int = 0
    recorded: int = 0
    archived: int = 0
    light_processed: int = 0
    full_selected: int = 0
    full_analysed: int = 0
    escalated: int = 0
    analysed: int = 0  # Backward-compatible alias for full_analysed.
    review_required: int = 0
    routine_persisted: int = 0  # Backward-compatible archive counter.
    deferred: int = 0
    blocked: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    processed_source_ids: list[str] = field(default_factory=list)
    failed_source_ids: list[str] = field(default_factory=list)


class DailyAIMIngestionService:
    """Record every AIM RNS, screen cheaply, and reserve Analyst 3.3 for FULL items."""

    def __init__(
        self,
        *,
        source: InvestegateDailyAIMSource,
        repository: IntelligenceRepository,
        pipeline: FoundationPipeline,
        max_ai_items: int = 36,
        progress: Callable[[str], None] | None = None,
        triage_repository: TriageRepository | None = None,
    ) -> None:
        self.source = source
        self.repository = repository
        self.pipeline = pipeline
        self.max_ai_items = max(3, max_ai_items)
        self.progress = progress
        self.triage = triage_repository or TriageRepository(repository.session_factory)

    def _emit(self, message: str) -> None:
        if self.progress is not None:
            self.progress(message)

    def _metadata_input(self, item: CatalogueAnnouncement, *, reason: str) -> AnnouncementInput:
        return AnnouncementInput(
            source_id=item.source_id,
            ticker=item.ticker,
            company=item.company,
            published_at=item.published_at,
            title=item.title,
            text=f"Regulatory announcement catalogue record: {item.title}.",
            source_url=item.source_url,
            source_urls=[item.source_url] if item.source_url else [],
            source_note=reason,
            evidence_status="metadata-only",
            rns_type="Other",
            categories=item.categories,
        )

    def _persist_archive(self, item: CatalogueAnnouncement, decision: TriageDecision) -> None:
        """Keep routine rows visible without spending evidence or Analyst 3.3 calls."""

        reason = decision.reason + " Stored as ARCHIVE without deep AI processing."
        announcement = self._metadata_input(item, reason=reason)
        note = routine_note(announcement, reason=reason)
        self.repository.save_analysis(
            announcement,
            note,
            prompt_version=self.pipeline.prompt_version,
            model_version="deterministic-archive",
        )

    @staticmethod
    def _context(values: dict[str, object]) -> TriageContext:
        return TriageContext(
            recent_director_dealings=int(values.get("recent_director_dealings") or 0),
            recent_adverse_trading=bool(values.get("recent_adverse_trading")),
            latest_revenue_value=str(values.get("latest_revenue_value") or ""),
            latest_share_count_value=str(values.get("latest_share_count_value") or ""),
        )

    def run(self, day: date | None = None) -> DailyIngestionResult:
        day = day or datetime.now(LONDON).date()
        self._emit(f"Discovering AIM announcements for {day.isoformat()}")
        catalogue, source_warnings = self.source.list_announcements(day)
        known = known_source_ids(self.repository, [item.source_id for item in catalogue])
        pending = [item for item in catalogue if item.source_id not in known]

        result = DailyIngestionResult(
            day=day,
            discovered=len(catalogue),
            already_known=len(known),
            warnings=list(source_warnings),
        )
        self._emit(
            f"Catalogue discovered={result.discovered} known={result.already_known} pending={len(pending)}"
        )
        if not pending:
            return result

        decisions: dict[str, TriageDecision] = {
            item.source_id: initial_triage(item) for item in pending
        }
        recordable: list[CatalogueAnnouncement] = []
        for item in pending:
            try:
                self.triage.record_catalogue(item, decisions[item.source_id])
            except Exception as exc:
                result.failed += 1
                result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"{item.ticker} {item.source_id}: catalogue persistence failed: "
                    f"{type(exc).__name__}: {exc}"[:700]
                )
                continue
            result.recorded += 1
            recordable.append(item)

        archive = [
            item for item in recordable if decisions[item.source_id].processing_level == "ARCHIVE"
        ]
        light = [
            item for item in recordable if decisions[item.source_id].processing_level == "LIGHT"
        ]
        initial_full = [
            item for item in recordable if decisions[item.source_id].processing_level == "FULL"
        ]
        self._emit(
            f"Triage recorded={result.recorded} archive={len(archive)} light={len(light)} full={len(initial_full)}"
        )

        for item in archive:
            try:
                self._persist_archive(item, decisions[item.source_id])
                result.archived += 1
                result.routine_persisted += 1
                result.processed_source_ids.append(item.source_id)
            except Exception as exc:
                result.failed += 1
                result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"{item.ticker} {item.source_id}: archive persistence failed: "
                    f"{type(exc).__name__}: {exc}"[:700]
                )
        if archive:
            self._emit(f"Archive complete={result.archived} failed={result.failed}")

        selected_initial = sorted(
            initial_full,
            key=lambda item: (decisions[item.source_id].score, item.published_at),
            reverse=True,
        )[: self.max_ai_items]
        result.full_selected = len(selected_initial)
        result.deferred = max(0, len(initial_full) - len(selected_initial))
        if result.deferred:
            result.warnings.append(
                f"{result.deferred} FULL announcement(s) deferred by MAX_AI_ITEMS={self.max_ai_items}; "
                "metadata/triage are stored and the announcements remain retryable."
            )
        self._process_full(selected_initial, result=result)

        escalated_documents: list[tuple[CatalogueAnnouncement, AnnouncementInput, TriageDecision]] = []
        if light:
            batch_size = max(1, int(getattr(self.source, "deep_batch_size", 5)))
            batch_count = (len(light) + batch_size - 1) // batch_size
            for batch_index, start in enumerate(range(0, len(light), batch_size), start=1):
                batch = light[start : start + batch_size]
                self._emit(
                    f"LIGHT evidence batch {batch_index}/{batch_count} size={len(batch)} "
                    f"tickers={','.join(item.ticker for item in batch)}"
                )
                result.warnings.extend(self.source.prepare_documents(batch))
                for item in batch:
                    initial = decisions[item.source_id]
                    try:
                        announcement = self.source.fetch_document(item)
                        context = self._context(
                            self.triage.company_context(item.ticker, before=item.published_at)
                        )
                        decision = assess_light(
                            announcement,
                            context=context,
                            initial=initial,
                        )
                        self.triage.record_document(announcement, decision)
                    except EvidenceUnavailableError as exc:
                        escalation = TriageDecision(
                            triage_class=initial.triage_class,
                            processing_level="FULL",
                            reason=initial.reason,
                            score=max(initial.score, 80),
                            escalated=True,
                            escalation_reason="LIGHT evidence unavailable; fail safe to FULL retry.",
                        )
                        self.triage.update_decision(item.source_id, escalation)
                        result.blocked += 1
                        result.failed_source_ids.append(item.source_id)
                        result.warnings.append(
                            f"{item.ticker} {item.source_id}: light evidence unavailable and escalated for retry: {exc}"[:700]
                        )
                        continue
                    except Exception as exc:
                        result.failed += 1
                        result.failed_source_ids.append(item.source_id)
                        result.warnings.append(
                            f"{item.ticker} {item.source_id}: light screening failed: "
                            f"{type(exc).__name__}: {exc}"[:700]
                        )
                        continue

                    if decision.processing_level == "FULL":
                        result.escalated += 1
                        escalated_documents.append((item, announcement, decision))
                    else:
                        result.light_processed += 1
                        result.processed_source_ids.append(item.source_id)

        remaining_capacity = max(0, self.max_ai_items - result.full_selected)
        selected_escalated = sorted(
            escalated_documents,
            key=lambda value: (value[2].score, value[0].published_at),
            reverse=True,
        )[:remaining_capacity]
        deferred_escalated = max(0, len(escalated_documents) - len(selected_escalated))
        result.deferred += deferred_escalated
        if deferred_escalated:
            result.warnings.append(
                f"{deferred_escalated} escalated LIGHT announcement(s) await FULL analysis; "
                "evidence is stored and they remain retryable."
            )
        result.full_selected += len(selected_escalated)
        for item, announcement, _decision in selected_escalated:
            self._process_document(item, announcement, result=result)

        self._emit(
            "Newsroom funnel complete "
            f"archive={result.archived} light={result.light_processed} escalated={result.escalated} "
            f"full={result.full_analysed} deferred={result.deferred} blocked={result.blocked} failed={result.failed}"
        )
        return result

    def _process_full(
        self,
        items: list[CatalogueAnnouncement],
        *,
        result: DailyIngestionResult,
    ) -> None:
        if not items:
            return
        batch_size = max(1, int(getattr(self.source, "deep_batch_size", 5)))
        batch_count = (len(items) + batch_size - 1) // batch_size
        for batch_index, start in enumerate(range(0, len(items), batch_size), start=1):
            batch = items[start : start + batch_size]
            self._emit(
                f"FULL evidence batch {batch_index}/{batch_count} size={len(batch)} "
                f"tickers={','.join(item.ticker for item in batch)}"
            )
            result.warnings.extend(self.source.prepare_documents(batch))
            for item in batch:
                try:
                    announcement = self.source.fetch_document(item)
                    self.triage.record_document(announcement, TriageDecision(
                        triage_class="FULL",
                        processing_level="FULL",
                        reason="High-signal event selected for full analysis.",
                        score=90,
                    ))
                except EvidenceUnavailableError as exc:
                    result.blocked += 1
                    result.failed_source_ids.append(item.source_id)
                    result.warnings.append(
                        f"{item.ticker} {item.source_id}: evidence unavailable and left retryable: {exc}"[:700]
                    )
                    continue
                except Exception as exc:
                    result.failed += 1
                    result.failed_source_ids.append(item.source_id)
                    result.warnings.append(
                        f"{item.ticker} {item.source_id}: evidence retrieval failed: "
                        f"{type(exc).__name__}: {exc}"[:700]
                    )
                    continue
                self._process_document(item, announcement, result=result)

    def _process_document(
        self,
        item: CatalogueAnnouncement,
        announcement: AnnouncementInput,
        *,
        result: DailyIngestionResult,
    ) -> None:
        try:
            persisted = self.pipeline.process(announcement)
        except (EvidenceUnavailableError, AnalysisBlockedError) as exc:
            result.blocked += 1
            result.failed_source_ids.append(item.source_id)
            result.warnings.append(
                f"{item.ticker} {item.source_id}: full analysis blocked and left retryable: "
                f"{type(exc).__name__}: {exc}"[:700]
            )
            return
        except Exception as exc:
            result.failed += 1
            result.failed_source_ids.append(item.source_id)
            result.warnings.append(
                f"{item.ticker} {item.source_id}: full analysis failed: "
                f"{type(exc).__name__}: {exc}"[:700]
            )
            return

        result.full_analysed += 1
        result.analysed += 1
        if persisted.quality_status == "review":
            result.review_required += 1
        result.processed_source_ids.append(persisted.source_id)
        self._emit(
            f"Stored FULL {item.ticker} source_id={persisted.source_id} quality={persisted.quality_status}"
        )
