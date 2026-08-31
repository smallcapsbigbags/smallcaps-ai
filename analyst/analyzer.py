from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, Sequence

from analyst.intelligence_policy import (
    AnalystIntelligenceBundle,
    detect_analytical_tensions,
)
from analyst.kpi_profiles import infer_kpi_profile
from analyst.models import AnalystNote, AnnouncementInput
from analyst.review_policy import ReviewDecision, decide_consistency_review


class AnalystEngine(Protocol):
    model_name: str

    def analyse(
        self,
        announcement: AnnouncementInput,
        prior_context: Sequence[dict[str, object]],
    ) -> AnalystNote: ...


class OpenAIAnalystEngine:
    """Structured analyst engine with memory, KPI intelligence and routed review."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt_path: Path | None = None,
        style_prompt_path: Path | None = None,
        decision_prompt_path: Path | None = None,
        override_prompt_path: Path | None = None,
        memory_prompt_path: Path | None = None,
        intelligence_prompt_path: Path | None = None,
        editorial_prompt_path: Path | None = None,
        facts_prompt_path: Path | None = None,
        review_prompt_path: Path | None = None,
        timeout_seconds: int = 180,
        max_output_tokens: int = 12_000,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for live analysis")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model_name = model
        self.max_output_tokens = max(2_000, max_output_tokens)
        self.initial_analysis_calls = 0
        self.consistency_review_calls = 0
        self.last_review_decision: ReviewDecision | None = None
        prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        self.prompt_path = prompt_path or (prompts_dir / "ANALYST_ENGINE_V2.md")
        self.style_prompt_path = style_prompt_path or (
            prompts_dir / "PLAIN_ENGLISH_ANALYST_V1.md"
        )
        self.decision_prompt_path = decision_prompt_path or (
            prompts_dir / "GOLD_STANDARD_ANALYST_V1.md"
        )
        self.override_prompt_path = override_prompt_path or (
            prompts_dir / "GOLD_STANDARD_OVERRIDES_V1.md"
        )
        self.memory_prompt_path = memory_prompt_path or (
            prompts_dir / "COMPANY_MEMORY_ANALYST_V1.md"
        )
        self.intelligence_prompt_path = intelligence_prompt_path or (
            prompts_dir / "ANALYST_INTELLIGENCE_LAYER_V1.md"
        )
        self.editorial_prompt_path = editorial_prompt_path or (
            prompts_dir / "EDITORIAL_OUTPUT_CONTRACT_V1.md"
        )
        self.facts_prompt_path = facts_prompt_path or (
            prompts_dir / "FACTS_NO_FLUFF_OUTPUT_CONTRACT_V1.md"
        )
        self.review_prompt_path = review_prompt_path or (
            prompts_dir / "ANALYST_CONSISTENCY_REVIEW_V1.md"
        )
        core_prompt = self.prompt_path.read_text(encoding="utf-8")
        style_prompt = self.style_prompt_path.read_text(encoding="utf-8")
        decision_prompt = self.decision_prompt_path.read_text(encoding="utf-8")
        override_prompt = self.override_prompt_path.read_text(encoding="utf-8")
        memory_prompt = self.memory_prompt_path.read_text(encoding="utf-8")
        intelligence_prompt = self.intelligence_prompt_path.read_text(
            encoding="utf-8"
        )
        editorial_prompt = self.editorial_prompt_path.read_text(encoding="utf-8")
        facts_prompt = self.facts_prompt_path.read_text(encoding="utf-8")
        consistency_prompt = self.review_prompt_path.read_text(encoding="utf-8")
        # Keep the deep internal AnalystNote. The Facts. No fluff. contract is
        # deliberately last so it controls the public-facing wording and evidence
        # discipline without weakening the richer analyst, memory or validation rules.
        self.system_prompt = "\n\n".join(
            (
                core_prompt,
                style_prompt,
                decision_prompt,
                override_prompt,
                memory_prompt,
                intelligence_prompt,
                editorial_prompt,
                facts_prompt,
            )
        )
        self.review_prompt = "\n\n".join(
            (
                consistency_prompt,
                memory_prompt,
                intelligence_prompt,
                editorial_prompt,
                facts_prompt,
            )
        )

    @property
    def analyst_model_calls(self) -> int:
        return self.initial_analysis_calls + self.consistency_review_calls

    @property
    def consistency_reviews_avoided(self) -> int:
        return max(0, self.initial_analysis_calls - self.consistency_review_calls)

    def model_call_stats(self) -> dict[str, int]:
        return {
            "initial_calls": self.initial_analysis_calls,
            "review_calls": self.consistency_review_calls,
            "reviews_avoided": self.consistency_reviews_avoided,
            "total_calls": self.analyst_model_calls,
        }

    @staticmethod
    def _expected_coverage_status(
        prior_context: Sequence[dict[str, object]],
    ) -> str:
        for record in prior_context:
            if record.get("context_type") != "company_memory_snapshot":
                continue
            status = str(record.get("coverage_status") or "building")
            return "established" if status == "established" else "building"
        return "building"

    def _normalise_coverage(
        self,
        note: AnalystNote,
        prior_context: Sequence[dict[str, object]],
    ) -> AnalystNote:
        expected_coverage = self._expected_coverage_status(prior_context)
        if note.what_changed.coverage_status == expected_coverage:
            return note
        return note.model_copy(
            update={
                "what_changed": note.what_changed.model_copy(
                    update={"coverage_status": expected_coverage}
                )
            }
        )

    def _require_source_id(
        self,
        note: AnalystNote,
        announcement: AnnouncementInput,
        *,
        stage: str,
    ) -> None:
        if note.source_id != announcement.source_id:
            raise RuntimeError(
                f"OpenAI did not preserve source_id during {stage}: "
                f"expected {announcement.source_id!r}, got {note.source_id!r}"
            )

    def _review_note(
        self,
        *,
        announcement: AnnouncementInput,
        prior_context: Sequence[dict[str, object]],
        draft: AnalystNote,
        intelligence: AnalystIntelligenceBundle,
    ) -> AnalystNote:
        review_payload = {
            "announcement": announcement.model_dump(mode="json"),
            "eligible_prior_context": list(prior_context),
            "draft_analyst_note": draft.model_dump(mode="json"),
            "deterministic_analyst_intelligence": intelligence.to_review_record(),
        }
        self.consistency_review_calls += 1
        response = self.client.responses.parse(
            model=self.model_name,
            instructions=self.review_prompt,
            input=(
                "Audit this draft against the exact same evidence, company memory and "
                "deterministic analyst-intelligence checks. Verify each heuristic finding "
                "before using it. Correct only real consistency, comparator, Impact, KPI, "
                "calculation, management-promise, coverage-status, plain-English or "
                "editorial-output-contract problems, including Facts. No fluff. contract "
                "violations. Do not invent a missing sector KPI, add outside information or "
                "change a defensible judgement merely to create a different opinion. The "
                "final headline and takeaway must be compact investor shorthand; first three key facts "
                "must stay feed-ready; key_facts must retain all decision-useful material facts; "
                "what_changed must use only supported comparators; unsupported inference or speculation must be removed. "
                "Return the complete corrected AnalystNote.\n\n"
                + json.dumps(review_payload, ensure_ascii=False)
            ),
            text_format=AnalystNote,
            max_output_tokens=self.max_output_tokens,
            store=False,
        )
        reviewed = response.output_parsed
        if reviewed is None:
            raise RuntimeError(
                "OpenAI returned no structured AnalystNote from consistency review"
            )
        self._require_source_id(reviewed, announcement, stage="consistency review")
        return self._normalise_coverage(reviewed, prior_context)

    def analyse(
        self,
        announcement: AnnouncementInput,
        prior_context: Sequence[dict[str, object]],
    ) -> AnalystNote:
        profile = infer_kpi_profile(announcement, prior_context)
        payload = {
            "announcement": announcement.model_dump(mode="json"),
            "eligible_prior_context": list(prior_context),
            "analyst_intelligence_profile": profile.to_context_record(),
        }
        self.initial_analysis_calls += 1
        response = self.client.responses.parse(
            model=self.model_name,
            instructions=self.system_prompt,
            input=(
                "Analyse this point-in-time UK regulatory announcement using only the "
                "supplied evidence and eligible prior context. Use the deterministic KPI "
                "profile as a checklist, not as company-reported evidence. When a company-"
                "memory snapshot is supplied, test the strongest valid prior comparator, "
                "guidance position and open management promises without letting old "
                "information displace today's main change. Think like a sceptical, "
                "commercially minded UK small-cap analyst, apply the gold-standard decision "
                "pass and benchmark-driven overrides, and write in compact investor English. "
                "Before choosing Impact, test the relationship between the sector's meaningful "
                "top line, profit, margin, cash and funding. Do the 1–3 most useful safe "
                "calculations when verified inputs support them, show the inputs, and keep "
                "reported facts, calculations and Smallcaps.ai interpretation separate. "
                "Treat takeaway as the public Company News take: target 20–40 words, hard "
                "maximum 45, no chatbot filler. Keep key_facts complete even when the take is "
                "short. State a directional What Changed only when a reliable comparator or "
                "explicit current-state transition supports it; otherwise establish today's "
                "baseline. Use the canonical company-news taxonomy and the attached Facts. "
                "No fluff. output contract. Explain important specialist concepts only in the "
                "structured concept explanations. Do not expose private reasoning.\n\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
            text_format=AnalystNote,
            max_output_tokens=self.max_output_tokens,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no structured AnalystNote")
        self._require_source_id(parsed, announcement, stage="initial analysis")

        findings = detect_analytical_tensions(
            announcement,
            parsed,
            prior_context,
            profile=profile,
        )
        intelligence = AnalystIntelligenceBundle(
            profile=profile,
            findings=findings,
        )

        try:
            review_decision = decide_consistency_review(
                announcement,
                parsed,
                prior_context=prior_context,
                intelligence=intelligence,
            )
        except Exception as exc:
            # Cost optimisation must fail closed. If the deterministic policy itself
            # cannot prove a single pass is safe, spend the review call.
            review_decision = ReviewDecision(
                mode="review",
                reasons=(
                    f"review policy failed closed: {type(exc).__name__}",
                ),
            )
        self.last_review_decision = review_decision

        if review_decision.requires_review:
            final_note = self._review_note(
                announcement=announcement,
                prior_context=prior_context,
                draft=parsed,
                intelligence=intelligence,
            )
        else:
            final_note = self._normalise_coverage(parsed, prior_context)

        references = list(
            dict.fromkeys(
                [
                    *final_note.source_references,
                    *parsed.source_references,
                    *announcement.source_urls,
                    *([announcement.source_url] if announcement.source_url else []),
                ]
            )
        )
        return final_note.model_copy(update={"source_references": references})
