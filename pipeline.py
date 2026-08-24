from __future__ import annotations

from analyst.analyzer import AnalystEngine
from analyst.classification import canonical_rns_type
from analyst.company_context import build_company_analysis_context
from analyst.evidence import validate_announcement_evidence
from analyst.guardrails import apply_analysis_guardrails
from analyst.models import AnnouncementInput, PersistedAnalysis, QualityReport
from analyst.monitoring_sheet import merge_monitoring_quality
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
        context_bundle = build_company_analysis_context(
            history,
            announcement,
            history_limit=7,
        )
        analysis_context = context_bundle.as_list()

        note = self.analyst_engine.analyse(announcement, analysis_context)
        if note.what_changed.coverage_status != context_bundle.expected_coverage_status:
            note = note.model_copy(
                update={
                    "what_changed": note.what_changed.model_copy(
                        update={
                            "coverage_status": context_bundle.expected_coverage_status
                        }
                    )
                }
            )

        # Taxonomy is a deterministic product contract. The model may identify a
        # useful event label, but unsupported/arbitrary labels and distress hidden
        # behind Other are normalised before quality checks and persistence.
        canonical_type = canonical_rns_type(announcement, note.rns_type)
        if canonical_type != note.rns_type:
            note = note.model_copy(update={"rns_type": canonical_type})

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
        quality = merge_monitoring_quality(quality, guarded_note)
        if quality.status == "blocked":
            raise AnalysisBlockedError(quality)
        return self.repository.save_analysis(
            announcement,
            guarded_note,
            prompt_version=self.prompt_version,
            model_version=self.analyst_engine.model_name,
            quality_report=quality,
        )
