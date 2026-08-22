from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Sequence

from pydantic import Field, model_validator

from analyst.company_memory import CompanyMemorySnapshot
from analyst.models import AnalystNote, AnnouncementInput, StrictModel

CaseChange = Literal["strengthens", "weakens", "unchanged", "unclear"]


class CompanyMemoryBenchmarkCase(StrictModel):
    id: str
    ticker: str
    company: str
    current_announcement: AnnouncementInput
    history: list[dict[str, object]] = Field(default_factory=list)
    expected_case_change: list[CaseChange]
    allowed_colours: list[str]
    min_impact_score: int = Field(ge=1, le=5)
    max_impact_score: int = Field(ge=1, le=5)
    required_points: list[str] = Field(default_factory=list)
    required_prior_source_ids: list[str] = Field(default_factory=list)
    required_claim_updates: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self) -> "CompanyMemoryBenchmarkCase":
        if self.current_announcement.ticker != self.ticker:
            raise ValueError("case ticker must match current announcement ticker")
        if self.min_impact_score > self.max_impact_score:
            raise ValueError("min_impact_score cannot exceed max_impact_score")
        if not self.expected_case_change:
            raise ValueError("expected_case_change must not be empty")
        if not self.allowed_colours:
            raise ValueError("allowed_colours must not be empty")
        if any(not statuses for statuses in self.required_claim_updates.values()):
            raise ValueError("required_claim_updates statuses must not be empty")
        return self


class CompanyMemoryJudgement(StrictModel):
    current_event_priority: int = Field(ge=0, le=20)
    historical_comparison: int = Field(ge=0, le=20)
    point_in_time_provenance: int = Field(ge=0, le=15)
    guidance_and_claims: int = Field(ge=0, le=15)
    calculations_and_kpis: int = Field(ge=0, le=15)
    impact_and_case_change: int = Field(ge=0, le=10)
    plain_english: int = Field(ge=0, le=5)
    main_change_identified: bool
    prior_context_used_safely: bool
    required_prior_sources_used: bool
    assessed_case_change: CaseChange
    impact_aligned: bool
    critical_failures: list[str] = Field(default_factory=list)
    top_strengths: list[str] = Field(default_factory=list)
    top_gaps: list[str] = Field(default_factory=list)
    upgrade_recommendations: list[str] = Field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(
            (
                self.current_event_priority,
                self.historical_comparison,
                self.point_in_time_provenance,
                self.guidance_and_claims,
                self.calculations_and_kpis,
                self.impact_and_case_change,
                self.plain_english,
            )
        )

    @property
    def passed(self) -> bool:
        return (
            self.total_score >= 85
            and self.current_event_priority >= 16
            and self.historical_comparison >= 16
            and self.point_in_time_provenance >= 12
            and not self.critical_failures
            and self.main_change_identified
            and self.prior_context_used_safely
            and self.required_prior_sources_used
            and self.impact_aligned
        )


class CompanyMemoryEvaluator:
    """Independent source-bound judge for the Phase 3 memory regression set."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for Company Memory evaluation")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model = model

    def evaluate(
        self,
        *,
        case: CompanyMemoryBenchmarkCase,
        snapshot: CompanyMemorySnapshot,
        note: AnalystNote,
        quality_status: str,
    ) -> CompanyMemoryJudgement:
        payload = {
            "benchmark_case": case.model_dump(mode="json"),
            "deterministic_memory_snapshot": snapshot.model_dump(mode="json"),
            "analyst_note": note.model_dump(mode="json"),
            "quality_status": quality_status,
        }
        instructions = """You are the independent Phase 3 Company Memory evaluator for Smallcaps.ai.

Judge only the supplied current announcement, earlier point-in-time records, deterministic memory snapshot and generated Analyst Note. Do not use outside knowledge.

The product goal is: explain today's genuinely new event, compare it with the strongest valid earlier disclosure, test management promises where today's evidence genuinely allows it, and preserve source provenance.

Score out of 100:
- Current event priority (20): today's main economic change remains the headline; history does not displace it.
- Historical comparison (20): strongest valid comparator, correct period/unit/currency/accounting basis, and clear Before/Today/Why it matters.
- Point-in-time provenance (15): no future information, no invented comparator, prior source IDs used where required, and current-RNS restatements identified correctly.
- Guidance and claims (15): guidance is not double-counted; open promises are updated only when justified and stable claim keys are preserved.
- Calculations and KPIs (15): investor-useful maths and relevant KPI divergence are handled accurately with visible inputs.
- Impact and investment-case change (10): colour/score and strengthens/weakens/unchanged/unclear judgement fit today's incremental evidence.
- Plain English (5): concise, normal-investor language with reported/calculated/view separation.

Critical failures are limited to serious errors: future-information leakage, invented material fact or comparator, materially wrong arithmetic, incompatible-period comparison presented as valid, wrong overall Impact direction, or falsely marking a management promise delivered/missed.

`required_points` are analytical behaviours, not additional factual evidence. `required_prior_source_ids` identifies earlier records that should be traceable in structured comparator fields or clearly used in the note. `required_claim_updates` identifies a stable claim key and allowed new statuses where today's RNS directly tests the promise.

Do not reward verbosity. A concise note can score fully. Return the structured CompanyMemoryJudgement."""
        response = self.client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=CompanyMemoryJudgement,
            max_output_tokens=5_000,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("Company Memory evaluator returned no structured result")
        return parsed


def deterministic_case_checks(
    case: CompanyMemoryBenchmarkCase,
    note: AnalystNote,
) -> dict[str, object]:
    """Enforce machine-checkable benchmark constraints before model judging."""

    errors: list[str] = []
    if note.impact_colour not in case.allowed_colours:
        errors.append(
            f"impact colour {note.impact_colour!r} not in {case.allowed_colours!r}"
        )
    if not case.min_impact_score <= note.impact_score <= case.max_impact_score:
        errors.append(
            f"impact score {note.impact_score} outside "
            f"{case.min_impact_score}-{case.max_impact_score}"
        )

    cited_sources = {
        fact.comparator_source_id
        for fact in note.key_facts
        if fact.comparator_source_id
    }
    cited_sources.update(
        event.previous_source_id
        for event in note.guidance_events
        if event.previous_source_id
    )
    missing_sources = sorted(set(case.required_prior_source_ids) - cited_sources)
    if missing_sources:
        errors.append(
            "required prior source IDs not used in structured comparators: "
            + ", ".join(missing_sources)
        )

    claim_statuses = {
        claim.claim_key: claim.status
        for claim in note.management_claims
        if claim.claim_key
    }
    for claim_key, allowed_statuses in case.required_claim_updates.items():
        status = claim_statuses.get(claim_key)
        if status not in allowed_statuses:
            errors.append(
                f"claim {claim_key!r} status {status!r} not in {allowed_statuses!r}"
            )

    return {
        "passed": not errors,
        "errors": errors,
        "cited_prior_source_ids": sorted(cited_sources),
        "claim_statuses": claim_statuses,
    }


def load_company_memory_cases(path: Path) -> list[CompanyMemoryBenchmarkCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Company Memory benchmark must be a JSON list")
    return [CompanyMemoryBenchmarkCase.model_validate(item) for item in raw]


def company_memory_acceptance(
    results: Sequence[CompanyMemoryJudgement],
) -> dict[str, object]:
    if not results:
        return {
            "passed": False,
            "average_score": 0.0,
            "minimum_score": 0,
            "passed_cases": 0,
            "critical_failures": 0,
            "safe_memory_cases": 0,
        }
    scores = [item.total_score for item in results]
    passed_cases = sum(1 for item in results if item.passed)
    critical = sum(len(item.critical_failures) for item in results)
    safe_memory = sum(1 for item in results if item.prior_context_used_safely)
    passed = (
        passed_cases == len(results)
        and sum(scores) / len(scores) >= 88
        and min(scores) >= 82
        and critical == 0
        and safe_memory == len(results)
    )
    return {
        "passed": passed,
        "average_score": round(sum(scores) / len(scores), 2),
        "minimum_score": min(scores),
        "passed_cases": passed_cases,
        "expected_cases": len(results),
        "critical_failures": critical,
        "safe_memory_cases": safe_memory,
    }
