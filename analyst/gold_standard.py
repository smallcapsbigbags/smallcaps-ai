from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Sequence

from pydantic import Field, model_validator

from analyst.models import AnalystNote, AnnouncementInput, StrictModel

CaseChange = Literal["strengthens", "weakens", "unchanged", "unclear"]


class RealBenchmarkCase(StrictModel):
    id: str
    day: str
    ticker: str
    headline_contains: list[str] = Field(default_factory=list)
    event_type: str
    allowed_colours: list[str]
    min_score: int = Field(ge=1, le=5)
    max_score: int = Field(ge=1, le=5)
    main_change: str
    human_reference: list[str]
    calculation_opportunities: list[str] = Field(default_factory=list)
    required_concepts: list[str] = Field(default_factory=list)
    case_change: CaseChange
    prior_context: list[dict[str, object]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_score_range(self) -> "RealBenchmarkCase":
        if self.min_score > self.max_score:
            raise ValueError("min_score cannot exceed max_score")
        if not self.headline_contains:
            raise ValueError("headline_contains must contain at least one matcher")
        return self


class GoldStandardJudgement(StrictModel):
    factual_grounding: int = Field(ge=0, le=20)
    investor_relevance: int = Field(ge=0, le=10)
    comparator_discipline: int = Field(ge=0, le=12)
    useful_calculations: int = Field(ge=0, le=10)
    commercial_interpretation: int = Field(ge=0, le=10)
    sector_event_kpi: int = Field(ge=0, le=8)
    balance_sheet_capital_control: int = Field(ge=0, le=8)
    uncertainty_and_explanation: int = Field(ge=0, le=6)
    investment_case_change: int = Field(ge=0, le=6)
    repeatability_and_next_steps: int = Field(ge=0, le=5)
    plain_english: int = Field(ge=0, le=5)
    main_change_identified: bool
    assessed_case_change: CaseChange
    impact_alignment: Literal["aligned", "too-low", "too-high", "wrong-direction"]
    critical_failures: list[str] = Field(default_factory=list)
    top_strengths: list[str] = Field(default_factory=list)
    top_gaps: list[str] = Field(default_factory=list)
    upgrade_recommendations: list[str] = Field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(
            (
                self.factual_grounding,
                self.investor_relevance,
                self.comparator_discipline,
                self.useful_calculations,
                self.commercial_interpretation,
                self.sector_event_kpi,
                self.balance_sheet_capital_control,
                self.uncertainty_and_explanation,
                self.investment_case_change,
                self.repeatability_and_next_steps,
                self.plain_english,
            )
        )

    @property
    def passed(self) -> bool:
        return (
            self.total_score >= 82
            and self.factual_grounding >= 16
            and not self.critical_failures
            and self.main_change_identified
        )


class GoldStandardEvaluator:
    """Independent structured judge for the Phase 2 human-grade benchmark."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        rubric_path: Path | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the gold-standard evaluator")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model = model
        self.rubric_path = rubric_path or (
            Path(__file__).resolve().parents[1] / "benchmarks" / "GOLD_STANDARD_RUBRIC.md"
        )
        self.rubric = self.rubric_path.read_text(encoding="utf-8")

    def evaluate(
        self,
        *,
        case: RealBenchmarkCase,
        announcement: AnnouncementInput,
        note: AnalystNote,
        prior_context: Sequence[dict[str, object]] = (),
    ) -> GoldStandardJudgement:
        payload = {
            "benchmark_case": case.model_dump(mode="json"),
            "announcement_evidence": announcement.model_dump(mode="json"),
            "eligible_prior_context": list(prior_context),
            "analyst_note": note.model_dump(mode="json"),
        }
        instructions = f"""You are the independent quality evaluator for Smallcaps.ai Phase 2.

Score the generated Analyst Note against the gold-standard rubric below. Judge only what the supplied announcement evidence and eligible prior context support.

IMPORTANT BOUNDARIES:
- `human_reference` describes the analytical behaviours and decision-useful points seen in paid human analyst reports. It is a benchmark target, NOT an additional factual source.
- Never treat a human-reference bullet as fact unless the same fact is supported by the announcement evidence or eligible prior context.
- Do not use outside knowledge.
- Do not reward verbosity. Depth should match importance.
- Do not penalise the note for declining a calculation when required inputs are not verified.
- Penalise invented numbers, invented comparators, fake precision, blurred reported/calculated/inferred provenance, buried adverse facts, or legal conclusions that the evidence does not support.
- Impact and market reaction are separate. Do not infer fundamental quality from share-price direction.
- `assessed_case_change` means whether TODAY'S NEW EVIDENCE strengthens, weakens, leaves unchanged, or leaves unclear the investment case. It is not Buy/Sell/Hold.
- `critical_failures` should contain only serious failures: invented material fact/number, materially wrong fact, unsupported comparator, inference presented as reported fact, missing explicit solvency/funding/profit-warning risk, or materially unsafe legal conclusion.
- Keep strengths/gaps/recommendations concise and specific enough to drive prompt or guardrail changes.

GOLD-STANDARD RUBRIC:
{self.rubric}
"""
        response = self.client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=GoldStandardJudgement,
            max_output_tokens=6_000,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("Gold-standard evaluator returned no structured result")
        return parsed


def load_real_benchmark_cases(path: Path) -> list[RealBenchmarkCase]:
    """Load locked cases plus explicit evidence-boundary corrections.

    Human reports sometimes rely on broker consensus or external context that the
    Smallcaps.ai V1 evidence contract intentionally excludes. Overrides are used
    only to remove such unsupported benchmark expectations; they do not replace
    difficult cases or add favourable facts.
    """

    raw = json.loads(path.read_text(encoding="utf-8"))
    overrides_path = path.with_name("real_case_overrides.json")
    overrides: dict[str, dict[str, object]] = {}
    if overrides_path.exists():
        loaded = json.loads(overrides_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("real_case_overrides.json must be a JSON object")
        overrides = {str(key): value for key, value in loaded.items()}

    cases: list[RealBenchmarkCase] = []
    for item in raw:
        case_id = str(item.get("id") or "")
        merged = {**item, **dict(overrides.get(case_id) or {})}
        cases.append(RealBenchmarkCase.model_validate(merged))
    return cases


def headline_matches(case: RealBenchmarkCase, headline: str) -> bool:
    clean = headline.lower()
    return any(token.lower() in clean for token in case.headline_contains)


def benchmark_acceptance(results: Sequence[GoldStandardJudgement]) -> dict[str, object]:
    if not results:
        return {
            "passed": False,
            "average_score": 0.0,
            "minimum_score": 0,
            "average_factual_grounding": 0.0,
            "main_change_hits": 0,
            "critical_failures": 0,
        }
    scores = [item.total_score for item in results]
    factual = [item.factual_grounding for item in results]
    main_hits = sum(1 for item in results if item.main_change_identified)
    critical = sum(len(item.critical_failures) for item in results)
    average = sum(scores) / len(scores)
    factual_average = sum(factual) / len(factual)
    passed = (
        average >= 85
        and min(scores) >= 75
        and factual_average >= 18
        and critical == 0
        and main_hits >= max(0, len(results) - 2)
    )
    return {
        "passed": passed,
        "average_score": round(average, 2),
        "minimum_score": min(scores),
        "average_factual_grounding": round(factual_average, 2),
        "main_change_hits": main_hits,
        "critical_failures": critical,
    }
