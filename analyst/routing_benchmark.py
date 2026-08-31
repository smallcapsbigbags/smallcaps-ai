from __future__ import annotations

import json
from typing import Literal, Sequence

from pydantic import Field, model_validator

from analyst.gold_standard import RealBenchmarkCase
from analyst.models import AnalystNote, AnnouncementInput, StrictModel


class RoutingPairJudgement(StrictModel):
    """Independent judgement of whether skipping review lost material quality."""

    acceptable_single_pass: bool
    factual_regression: bool = False
    material_fact_regression: bool = False
    impact_regression: bool = False
    comparator_regression: bool = False
    what_changed_regression: bool = False
    unsupported_inference_regression: bool = False
    material_regressions: list[str] = Field(default_factory=list)
    reviewed_improvements: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consistency(self) -> "RoutingPairJudgement":
        has_regression = any(
            (
                self.factual_regression,
                self.material_fact_regression,
                self.impact_regression,
                self.comparator_regression,
                self.what_changed_regression,
                self.unsupported_inference_regression,
            )
        )
        if self.acceptable_single_pass and has_regression:
            raise ValueError(
                "acceptable_single_pass cannot be true when a material regression flag is true"
            )
        if has_regression and not self.material_regressions:
            raise ValueError("material regression flags require a concise explanation")
        return self


class RoutingRegressionEvaluator:
    """Pairwise judge for routed one-pass output versus a forced shadow review."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the routing regression evaluator")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model = model

    def compare(
        self,
        *,
        case: RealBenchmarkCase,
        announcement: AnnouncementInput,
        routed_note: AnalystNote,
        reviewed_note: AnalystNote,
        prior_context: Sequence[dict[str, object]] = (),
    ) -> RoutingPairJudgement:
        payload = {
            "benchmark_case": case.model_dump(mode="json"),
            "announcement_evidence": announcement.model_dump(mode="json"),
            "eligible_prior_context": list(prior_context),
            "routed_single_pass_note": routed_note.model_dump(mode="json"),
            "forced_shadow_review_note": reviewed_note.model_dump(mode="json"),
        }
        instructions = """You are the independent Pass 4 regression judge for Smallcaps.ai.

The ROUTED note is what would be published when Analyst 3.4 skips its second consistency review. The SHADOW note is the same first-pass analysis after forcing the old second consistency review. The shadow note is NOT presumed to be better.

Judge only against the supplied announcement evidence and eligible prior context. Do not use outside knowledge. The human benchmark reference is a behaviour target, never a factual source.

Set acceptable_single_pass=true when omitting the second review causes no MATERIAL loss of decision-useful quality. Ignore harmless wording, ordering, punctuation and stylistic differences.

A material regression includes any of the following when the shadow review genuinely fixes it:
- a materially wrong, missing or invented fact;
- omission of a decision-useful material fact;
- wrong signal direction or materially wrong impact judgement;
- unsupported or missing comparator discipline;
- a weaker or misleading What Changed / baseline conclusion;
- unsupported inference or speculation that the shadow removes;
- burying a profit warning, funding/solvency risk, dilution, takeover condition, cash/debt issue or other dominant investment consequence.

Do NOT call it a regression merely because the shadow adds more words, makes a different defensible judgement, or adds immaterial detail. Do NOT reward verbosity. If both notes are defensible and equally decision-useful, the one-pass route is acceptable.

Return concise regression/improvement bullets. Material regression flags must only be used for differences that would justify paying for the second analyst call in production."""
        response = self.client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=RoutingPairJudgement,
            max_output_tokens=3_000,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("Routing regression evaluator returned no structured result")
        return parsed


class RoutingAuditRecord(StrictModel):
    case_id: str
    decision_mode: Literal["single-pass", "review"]
    decision_reasons: list[str] = Field(default_factory=list)
    routed_publishable: bool
    routed_gold_passed: bool
    routed_score: int = Field(ge=0, le=100)
    routed_factual_grounding: int = Field(ge=0, le=20)
    routed_critical_failures: list[str] = Field(default_factory=list)
    routed_impact_alignment: str
    routed_impact_colour: str
    routed_impact_score: int = Field(ge=1, le=5)
    shadow_reviewed: bool = False
    shadow_publishable: bool | None = None
    shadow_gold_passed: bool | None = None
    shadow_score: int | None = Field(default=None, ge=0, le=100)
    shadow_factual_grounding: int | None = Field(default=None, ge=0, le=20)
    shadow_impact_colour: str | None = None
    shadow_impact_score: int | None = Field(default=None, ge=1, le=5)
    pairwise_acceptable: bool | None = None
    pairwise_material_regressions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shadow_shape(self) -> "RoutingAuditRecord":
        if self.decision_mode == "single-pass":
            required = (
                self.shadow_publishable,
                self.shadow_gold_passed,
                self.shadow_score,
                self.shadow_factual_grounding,
                self.shadow_impact_colour,
                self.shadow_impact_score,
                self.pairwise_acceptable,
            )
            if not self.shadow_reviewed or any(value is None for value in required):
                raise ValueError("single-pass routing audit requires a complete forced shadow review")
        return self


def routing_benchmark_acceptance(
    records: Sequence[RoutingAuditRecord],
    *,
    expected_cases: int,
    min_single_pass_cases: int = 1,
) -> dict[str, object]:
    """Loss-averse acceptance gate for the Pass 4 routing quality audit."""

    failures: dict[str, list[str]] = {}
    single_pass = [item for item in records if item.decision_mode == "single-pass"]
    reviewed = [item for item in records if item.decision_mode == "review"]

    for item in records:
        reasons: list[str] = []
        if not item.routed_publishable:
            reasons.append("routed note is not publishable")
        if not item.routed_gold_passed:
            reasons.append("routed note failed the human-grade gold-standard case gate")
        if item.routed_critical_failures:
            reasons.append("routed note has a critical factual/evidence failure")
        if item.routed_impact_alignment == "wrong-direction":
            reasons.append("routed impact is wrong-direction")

        if item.decision_mode == "single-pass":
            if item.pairwise_acceptable is not True:
                reasons.append("forced shadow review exposed a material regression")
            if item.pairwise_material_regressions:
                reasons.append("pairwise judge identified material regression detail")
            if item.shadow_score is not None and item.shadow_score - item.routed_score > 3:
                reasons.append("shadow review improves gold-standard score by more than 3 points")
            if (
                item.shadow_factual_grounding is not None
                and item.shadow_factual_grounding - item.routed_factual_grounding > 1
            ):
                reasons.append("shadow review improves factual grounding by more than 1 point")
            if (
                item.shadow_impact_colour is not None
                and item.shadow_impact_colour != item.routed_impact_colour
            ):
                reasons.append("shadow review changes impact direction/colour")
            if (
                item.shadow_impact_score is not None
                and abs(item.shadow_impact_score - item.routed_impact_score) >= 2
            ):
                reasons.append("shadow review changes impact materiality by two or more levels")

        if reasons:
            failures[item.case_id] = list(dict.fromkeys(reasons))

    if len(records) != expected_cases:
        failures["__case_count__"] = [
            f"expected {expected_cases} cases but scored {len(records)}"
        ]
    if len(single_pass) < min_single_pass_cases:
        failures["__savings_proof__"] = [
            f"only {len(single_pass)} single-pass case(s); need at least {min_single_pass_cases} to prove review savings"
        ]

    baseline_two_pass_calls = expected_cases * 2
    routed_calls = len(records) + len(reviewed)
    avoided_calls = len(single_pass)
    reduction_pct = (
        round((avoided_calls / baseline_two_pass_calls) * 100.0, 1)
        if baseline_two_pass_calls
        else 0.0
    )

    return {
        "passed": not failures,
        "expected_cases": expected_cases,
        "scored_cases": len(records),
        "single_pass_cases": [item.case_id for item in single_pass],
        "reviewed_cases": [item.case_id for item in reviewed],
        "single_pass_count": len(single_pass),
        "reviewed_count": len(reviewed),
        "baseline_two_pass_analyst_calls": baseline_two_pass_calls,
        "routed_analyst_calls": routed_calls,
        "analyst_calls_avoided": avoided_calls,
        "analyst_call_reduction_pct": reduction_pct,
        "regression_cases": failures,
    }
