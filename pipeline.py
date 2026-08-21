from __future__ import annotations

from analyst.analyzer import AnalystEngine
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
    """Source → evidence gate → context → analysis → guardrails → quality → Postgres."""

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
            announcement, min_chars=self.min_evidence_chars
        )
        history = self.repository.load_prior_context(
            announcement.ticker,
            before=announcement.published_at,
        )
        selected_context = select_prior_context(history, [announcement])
        note = self.analyst_engine.analyse(announcement, selected_context)
        guarded_note = apply_analysis_guardrails(announcement, note)
        quality = assess_analysis_quality(
            announcement,
            guarded_note,
            prior_context=selected_context,
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
