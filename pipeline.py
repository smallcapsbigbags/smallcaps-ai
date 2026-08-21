from __future__ import annotations

from analyst.analyzer import AnalystEngine
from analyst.context_selector import select_prior_context
from analyst.guardrails import apply_analysis_guardrails
from analyst.models import AnnouncementInput, PersistedAnalysis
from database.repository import IntelligenceRepository


class FoundationPipeline:
    """Pass 1 orchestration: source → context → analysis → guardrails → Postgres."""

    def __init__(
        self,
        *,
        repository: IntelligenceRepository,
        analyst_engine: AnalystEngine,
        prompt_version: str,
    ) -> None:
        self.repository = repository
        self.analyst_engine = analyst_engine
        self.prompt_version = prompt_version

    def process(self, announcement: AnnouncementInput) -> PersistedAnalysis:
        history = self.repository.load_prior_context(
            announcement.ticker,
            before=announcement.published_at,
        )
        selected_context = select_prior_context(history, [announcement])
        note = self.analyst_engine.analyse(announcement, selected_context)
        guarded_note = apply_analysis_guardrails(announcement, note)
        return self.repository.save_analysis(
            announcement,
            guarded_note,
            prompt_version=self.prompt_version,
            model_version=self.analyst_engine.model_name,
        )
