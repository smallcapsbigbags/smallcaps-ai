from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from analyst.classification import material_priority
from analyst.evidence import EvidenceUnavailableError
from analyst.triage import TriageDecision, triage_evidence, triage_metadata
from database.queries import known_source_ids
from database.repository import IntelligenceRepository
from database.triage_store import TriageRepository
from ingestion.investegate_daily import (
    CatalogueAnnouncement,
    InvestegateDailyAIMSource,
)
from pipeline import AnalysisBlockedError, FoundationPipeline

LONDON = ZoneInfo("Europe/London")


@dataclass
class DailyIngestionResult:
    day: date
    discovered: int = 0
    already_known: int = 0
    analysed: int = 0
    review_required: int = 0
    routine_persisted: int = 0  # backward-compatible alias for ARCHIVE records
    archived: int = 0
    light_processed: int = 0
    escalated_to_full: int = 0
    deferred: int = 0
    blocked: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    processed_source_ids: list[str] = field(default_factory=list)
    failed_source_ids: list[str] = field(default_factory=list)

    @property
    def analyst_calls_avoided(self) -> int:
        return self.archived + self.light_processed


class DailyAIMIngestionService:
    """Record everything → screen everything → analyse selectively → Postgres."""

    def __init__(
        self,
        *,
        source: InvestegateDailyAIMSource,
        repository: IntelligenceRepository,
        pipeline: FoundationPipeline,
        max_ai_items: int = 36,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.source = source
        self.repository = repository
        self.pipeline = pipeline
        self.max_ai_items = max(3, max_ai_items)
        self.progress = progress
        self.triage = TriageRepository(repository.session_factory)

    def _emit(self, message: str) -> None:
        if self.progress is not None:
            self.progress(message)

    def _record_all_pending(
        self,
        pending: list[CatalogueAnnouncement],
    ) -> dict[str, TriageDecision]:
        decisions: dict[str, TriageDecision] = {}
        for item in pending:
            decision = triage_metadata(item)
            # Fail closed here: no announcement may consume evidence/model work
            # until the durable newsroom ledger contains its catalogue provenance.
            self.triage.record_catalogue(item, decision)
            decisions[item.source_id] = decision
        return decisions

    def run(self, day: date | None = None) -> DailyIngestionResult:
        day = day or datetime.now(LONDON).date()
        self._emit(f"Discovering AIM announcements for {day.isoformat()}")
        catalogue, source_warnings = self.source.list_announcements(day)
        source_ids = [item.source_id for item in catalogue]
        analysed_known = known_source_ids(self.repository, source_ids)
        triage_known = self.triage.completed_source_ids(source_ids)
        known = analysed_known | triage_known
        pending = [item for item in catalogue if item.source_id not in known]

        result = DailyIngestionResult(
            day=day,
            discovered=len(catalogue),
            already_known=len(known),
            warnings=list(source_warnings),
        )
        self._emit(
            f"Catalogue discovered={result.discovered} known={result.already_known} "
            f"pending={len(pending)}"
        )

        if not pending:
            return result

        decisions = self._record_all_pending(pending)
        archive = [
            item
            for item in pending
            if decisions[item.source_id].processing_level == "archive"
        ]
        evidence_screen = [
            item
            for item in pending
            if decisions[item.source_id].processing_level in {"light", "full"}
        ]
        self._emit(
            f"Triage recorded={len(pending)} archive={len(archive)} "
            f"light={sum(decisions[item.source_id].processing_level == 'light' for item in pending)} "
            f"full={sum(decisions[item.source_id].processing_level == 'full' for item in pending)}"
        )

        for item in archive:
            self.triage.mark_status(item.source_id, "complete")
            result.archived += 1
            result.routine_persisted += 1
            result.processed_source_ids.append(item.source_id)

        if not evidence_screen:
            return result

        # LIGHT screening still retrieves evidence, but deliberately avoids an
        # Analyst 3.3 inference call unless deterministic evidence/context triggers
        # an escalation. FULL metadata items are retrieved in the same batches.
        batch_size = max(1, int(getattr(self.source, "deep_batch_size", 5)))
        batch_count = (len(evidence_screen) + batch_size - 1) // batch_size
        full_candidates: list[tuple[CatalogueAnnouncement, object, TriageDecision]] = []

        for batch_index, start in enumerate(
            range(0, len(evidence_screen), batch_size), start=1
        ):
            batch = evidence_screen[start : start + batch_size]
            tickers = ",".join(item.ticker for item in batch)
            self._emit(
                f"Evidence screen {batch_index}/{batch_count} size={len(batch)} "
                f"tickers={tickers}"
            )
            try:
                result.warnings.extend(self.source.prepare_documents(batch))
            except Exception as exc:
                for item in batch:
                    self.triage.mark_status(item.source_id, "retryable")
                    result.failed += 1
                    result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"Evidence batch preparation failed; {len(batch)} item(s) left retryable: "
                    f"{type(exc).__name__}: {exc}"[:700]
                )
                continue

            for item in batch:
                initial = decisions[item.source_id]
                try:
                    announcement = self.source.fetch_document(item)
                except EvidenceUnavailableError as exc:
                    self.triage.mark_status(item.source_id, "retryable")
                    result.blocked += 1
                    result.failed_source_ids.append(item.source_id)
                    result.warnings.append(
                        f"{item.ticker} {item.source_id}: evidence unavailable and left retryable: {exc}"[:700]
                    )
                    continue
                except Exception as exc:
                    self.triage.mark_status(item.source_id, "retryable")
                    result.failed += 1
                    result.failed_source_ids.append(item.source_id)
                    result.warnings.append(
                        f"{item.ticker} {item.source_id}: evidence screening failed: "
                        f"{type(exc).__name__}: {exc}"[:700]
                    )
                    continue

                if initial.processing_level == "light":
                    try:
                        context = self.triage.company_context(
                            item.ticker,
                            before=item.published_at,
                        )
                        screened = triage_evidence(
                            item,
                            announcement.text,
                            context=context,
                        )
                    except Exception as exc:
                        self.triage.mark_status(item.source_id, "retryable")
                        result.failed += 1
                        result.failed_source_ids.append(item.source_id)
                        result.warnings.append(
                            f"{item.ticker} {item.source_id}: deterministic LIGHT screen failed and was left retryable: "
                            f"{type(exc).__name__}: {exc}"[:700]
                        )
                        continue
                    if screened.processing_level == "light":
                        self.triage.record_evidence(
                            announcement,
                            screened,
                            status="complete",
                        )
                        result.light_processed += 1
                        result.processed_source_ids.append(item.source_id)
                        continue
                    result.escalated_to_full += 1
                    decision = screened
                else:
                    decision = initial

                self.triage.record_evidence(
                    announcement,
                    decision,
                    status="recorded",
                )
                full_candidates.append((item, announcement, decision))

        if not full_candidates:
            self._emit(
                f"Triage complete archive={result.archived} light={result.light_processed} "
                f"full=0 avoided={result.analyst_calls_avoided}"
            )
            return result

        full_candidates.sort(
            key=lambda entry: (
                entry[2].priority,
                material_priority(entry[0]),
                entry[0].published_at,
            ),
            reverse=True,
        )
        selected = full_candidates[: self.max_ai_items]
        deferred = full_candidates[self.max_ai_items :]
        result.deferred = len(deferred)
        for item, _announcement, _decision in deferred:
            self.triage.mark_status(item.source_id, "queued")
        if deferred:
            result.warnings.append(
                f"{len(deferred)} full-analysis announcement(s) deferred by "
                f"MAX_AI_ITEMS={self.max_ai_items}; their triage/evidence records "
                "remain durable and retryable on the next run."
            )

        for item, announcement, _decision in selected:
            try:
                persisted = self.pipeline.process(announcement)
            except AnalysisBlockedError as exc:
                self.triage.mark_status(item.source_id, "retryable")
                result.blocked += 1
                result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"{item.ticker} {item.source_id}: analysis blocked and left retryable: "
                    f"{type(exc).__name__}: {exc}"[:700]
                )
                continue
            except Exception as exc:
                self.triage.mark_status(item.source_id, "retryable")
                result.failed += 1
                result.failed_source_ids.append(item.source_id)
                result.warnings.append(
                    f"{item.ticker} {item.source_id}: analysis failed: "
                    f"{type(exc).__name__}: {exc}"[:700]
                )
                continue

            self.triage.mark_status(item.source_id, "complete")
            result.analysed += 1
            if persisted.quality_status == "review":
                result.review_required += 1
            result.processed_source_ids.append(persisted.source_id)
            self._emit(
                f"Stored FULL {item.ticker} source_id={persisted.source_id} "
                f"quality={persisted.quality_status} analysed={result.analysed}"
            )

        self._emit(
            f"Newsroom funnel archive={result.archived} light={result.light_processed} "
            f"escalated={result.escalated_to_full} full={result.analysed} "
            f"avoided={result.analyst_calls_avoided} deferred={result.deferred}"
        )
        return result
