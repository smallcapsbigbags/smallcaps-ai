from __future__ import annotations

from analyst.analyzer import AnalystEngine
from analyst.company_context import build_prior_context_record
from analyst.company_memory import build_company_memory
from analyst.context_selector import select_prior_context
from analyst.evidence import validate_announcement_evidence
from analyst.guardrails import apply_analysis_guardrails
from analyst.models import AnnouncementInput, PersistedAnalysis, QualityReport
from analyst.quality import assess_analysis_quality
from database.repository import IntelligenceRepository


class AnalysisBlockedError(RuntimeError):
    """Raised when deterministic quality checks prohibit publication/persistence."""

    def __init__(self, report: QualityReport) -> None:
        self.report = report
        messages = "; ".join(flag.message for flag in report.flags) or "analysis blocked"
        super().__init__(messages)


class FoundationPipeline:
    """Source → evidence → company memory → analysis → quality → Postgres."""

    def __init__(
        self,
        *,
        repository: IntelligenceRepository,
        analyst_engine: AnalystEngine,
        prompt_version: str,
        min_evidence_chars: int = 40,
    ) -> None:
        self.repository = repository
        self.analyst_engine = analyst_engine
        self.prompt_version = prompt_version
        self.min_evidence_chars = max(1, min_evidence_chars)

    def process(self, announcement: AnnouncementInput) -> PersistedAnalysis:
        validate_announcement_evidence(
            announcement,
            min_chars=self.min_evidence_chars,
        )
        history = self.repository.load_prior_context(
            announcement.ticker,
            before=announcement.published_at,
        )

        analysis_context: list[dict[str, object]] = []
        expected_coverage = "building"
        if history:
            memory = build_company_memory(
                history,
                ticker=announcement.ticker,
                company=announcement.company,
                before=announcement.published_at,
            )
            selected_history = select_prior_context(
                history,
                [announcement],
                limit=7,
            )
            # The snapshot supplies continuity. Selected source-level records are
            # then reshaped so company disclosure, Smallcaps.ai calculations and
            # earlier analyst interpretation cannot be blurred together.
            prior_records = [
                build_prior_context_record(record)
                for record in selected_history
            ]
            analysis_context = [memory.to_context_record(), *prior_records]
            expected_coverage = memory.coverage_status

        note = self.analyst_engine.analyse(announcement, analysis_context)
        if note.what_changed.coverage_status != expected_coverage:
            note = note.model_copy(
                update={
                    "what_changed": note.what_changed.model_copy(
                        update={"coverage_status": expected_coverage}
                    )
                }
            )
        guarded_note = apply_analysis_guardrails(
            announcement,
            note,
            prior_context=analysis_context,
        )
        quality = assess_analysis_quality(
            announcement,
            guarded_note,
            prior_context=analysis_context,
        )
        if quality.status == "blocked":
            raise AnalysisBlockedError(quality)
        return self.repository.save_analysis(
            announcement,
            guarded_note,
            prompt_version=self.prompt_version,
            model_version=self.analyst_engine.model_name,
            quality_report=quality,
        )
