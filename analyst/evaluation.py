from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from analyst.models import AnalystNote, StrictModel


class BenchmarkExpectation(StrictModel):
    allowed_colours: list[str]
    min_score: int = Field(ge=1, le=5)
    max_score: int = Field(ge=1, le=5)
    required_any: list[list[str]] = Field(default_factory=list)


class BenchmarkCase(StrictModel):
    id: str
    ticker: str
    company: str
    title: str
    rns_type: str
    text: str
    prior_context: list[dict[str, object]] = Field(default_factory=list)
    expectation: BenchmarkExpectation


class BenchmarkResult(StrictModel):
    case_id: str
    passed: bool
    failures: list[str] = Field(default_factory=list)


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(item) for item in raw]


def evaluate_benchmark(
    case: BenchmarkCase,
    note: AnalystNote,
) -> BenchmarkResult:
    failures: list[str] = []

    if note.impact_colour not in case.expectation.allowed_colours:
        failures.append(
            f"colour {note.impact_colour!r} not in "
            f"{case.expectation.allowed_colours!r}"
        )
    if not (
        case.expectation.min_score
        <= note.impact_score
        <= case.expectation.max_score
    ):
        failures.append(
            f"score {note.impact_score} outside "
            f"{case.expectation.min_score}-{case.expectation.max_score}"
        )

    text = " ".join(
        [
            note.headline,
            note.takeaway,
            note.impact_rationale,
            note.what_changed.today,
            note.what_changed.read_through,
            note.analyst_view,
            *note.new_information,
            *note.supports_case,
            *note.challenges_case,
            *note.watch_items,
            *[
                " ".join(
                    [
                        fact.label,
                        fact.value,
                        fact.note,
                        fact.comparator,
                        fact.previous_value,
                    ]
                )
                for fact in note.key_facts
            ],
        ]
    ).lower()

    for group in case.expectation.required_any:
        if not any(term.lower() in text for term in group):
            failures.append(
                "missing required concept group: " + " | ".join(group)
            )

    return BenchmarkResult(
        case_id=case.id,
        passed=not failures,
        failures=failures,
    )
