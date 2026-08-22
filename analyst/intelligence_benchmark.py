from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from analyst.intelligence import detect_analytical_tensions
from analyst.kpi_profiles import infer_kpi_profile
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    GuidanceEvent,
    KeyFact,
    StrictModel,
    WhatChanged,
)


class IntelligenceBenchmarkCase(StrictModel):
    id: str
    expected_profile: str
    announcement: AnnouncementInput
    facts: list[KeyFact] = Field(default_factory=list)
    guidance_events: list[GuidanceEvent] = Field(default_factory=list)
    prior_context: list[dict[str, object]] = Field(default_factory=list)
    expected_finding_codes: list[str] = Field(default_factory=list)
    forbidden_finding_codes: list[str] = Field(default_factory=list)

    def build_note(self) -> AnalystNote:
        source_url = self.announcement.source_url
        return AnalystNote(
            source_id=self.announcement.source_id,
            rns_type=self.announcement.rns_type,
            impact_colour="amber",
            impact_score=2,
            impact_level="medium",
            impact_rationale="The disclosed relationships require analysis.",
            headline=self.announcement.title,
            takeaway="The announcement contains several decision-useful metrics.",
            key_facts=self.facts,
            guidance_events=self.guidance_events,
            what_changed=WhatChanged(
                before="Earlier performance provides the comparator.",
                today="The current announcement updates the operating position.",
                read_through="The relationship between the numbers needs testing.",
            ),
            analyst_view="The update should be assessed on the disclosed evidence.",
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=[source_url] if source_url else [],
            confidence=0.9,
        )


class IntelligenceBenchmarkResult(StrictModel):
    case_id: str
    passed: bool
    expected_profile: str
    actual_profile: str
    expected_finding_codes: list[str]
    actual_finding_codes: list[str]
    missing_finding_codes: list[str]
    forbidden_finding_codes_found: list[str]


def load_intelligence_cases(path: Path) -> list[IntelligenceBenchmarkCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Analyst Intelligence benchmark must be a JSON list")
    cases = [IntelligenceBenchmarkCase.model_validate(item) for item in raw]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Analyst Intelligence benchmark case IDs must be unique")
    return cases


def evaluate_intelligence_case(
    case: IntelligenceBenchmarkCase,
) -> IntelligenceBenchmarkResult:
    note = case.build_note()
    profile = infer_kpi_profile(case.announcement, case.prior_context)
    findings = detect_analytical_tensions(
        case.announcement,
        note,
        case.prior_context,
        profile=profile,
    )
    actual_codes = [item.code for item in findings]
    missing = sorted(set(case.expected_finding_codes) - set(actual_codes))
    forbidden = sorted(set(case.forbidden_finding_codes) & set(actual_codes))
    passed = (
        profile.profile_id == case.expected_profile
        and not missing
        and not forbidden
    )
    return IntelligenceBenchmarkResult(
        case_id=case.id,
        passed=passed,
        expected_profile=case.expected_profile,
        actual_profile=profile.profile_id,
        expected_finding_codes=case.expected_finding_codes,
        actual_finding_codes=actual_codes,
        missing_finding_codes=missing,
        forbidden_finding_codes_found=forbidden,
    )


def run_intelligence_benchmark(
    cases: list[IntelligenceBenchmarkCase],
) -> dict[str, Any]:
    results = [evaluate_intelligence_case(case) for case in cases]
    passed_cases = sum(1 for result in results if result.passed)
    acceptance = {
        "passed": passed_cases == len(results) and bool(results),
        "case_count": len(results),
        "passed_cases": passed_cases,
        "failed_cases": [result.case_id for result in results if not result.passed],
    }
    return {
        "acceptance": acceptance,
        "results": [result.model_dump(mode="json") for result in results],
    }
