from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from analyst.analyzer import OpenAIAnalystEngine
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    GuidanceEvent,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from analyst.review_policy import REVIEW_POLICY_VERSION, decide_consistency_review


def announcement(**updates) -> AnnouncementInput:
    values = {
        "source_id": "routing-1",
        "ticker": "ABC",
        "company": "ABC plc",
        "published_at": datetime(2026, 8, 31, 7, 0, tzinfo=timezone.utc),
        "title": "Contract Award",
        "text": "The company signed a £500,000 contract. Guidance is unchanged.",
        "source_url": "https://example.invalid/routing-1",
        "source_urls": ["https://example.invalid/routing-1"],
        "evidence_status": "complete",
        "rns_type": "Contracts",
    }
    values.update(updates)
    return AnnouncementInput(**values)


def note(**updates) -> AnalystNote:
    values = {
        "source_id": "routing-1",
        "rns_type": "Contracts",
        "impact_colour": "grey",
        "impact_score": 2,
        "impact_level": "medium",
        "impact_rationale": "The disclosed contract is modest and guidance is unchanged.",
        "impact_drivers": [
            ImpactDriver(
                dimension="operations",
                direction="neutral",
                significance=2,
                rationale="Contract value is £500,000 and guidance is unchanged.",
            )
        ],
        "headline": "£500k contract; guidance unchanged",
        "takeaway": "£500k contract signed. Guidance unchanged. No margin or revenue contribution disclosed.",
        "key_facts": [
            KeyFact(
                label="Contract value",
                metric="contract value",
                value="£500,000",
                basis="reported",
            ),
            KeyFact(
                label="Guidance",
                metric="guidance",
                value="Unchanged",
                basis="reported",
            ),
        ],
        "what_changed": WhatChanged(
            before="Coverage is building.",
            today="A £500,000 contract has been signed.",
            read_through="No material earnings change is disclosed.",
            coverage_status="building",
        ),
        "analyst_view": "Modest contract. No change to guidance and no disclosed margin contribution.",
        "disclosure_assessment": DisclosureAssessment(status="complete"),
        "source_references": ["https://example.invalid/routing-1"],
        "confidence": 0.92,
    }
    values.update(updates)
    return AnalystNote(**values)


def test_clean_low_materiality_draft_can_stop_after_one_pass() -> None:
    decision = decide_consistency_review(announcement(), note())
    assert decision.policy_version == REVIEW_POLICY_VERSION
    assert decision.mode == "single-pass"
    assert decision.requires_review is False


def test_materiality_three_plus_always_keeps_consistency_review() -> None:
    current = note(
        impact_colour="green",
        impact_score=3,
        impact_level="high",
        impact_rationale="The contract is material to current trading.",
        impact_drivers=[
            ImpactDriver(
                dimension="earnings",
                direction="favourable",
                significance=3,
                rationale="The contract is material to current trading.",
            )
        ],
    )
    decision = decide_consistency_review(announcement(), current)
    assert decision.requires_review
    assert any("materiality 3/5" in reason for reason in decision.reasons)


def test_structural_transactions_keep_review_even_if_first_pass_scores_low() -> None:
    current_announcement = announcement(
        title="Placing and Subscription",
        text="The company is raising £1m through a placing at 10p per share.",
        rns_type="Fundraising",
    )
    current_note = note(
        rns_type="Fundraising",
        headline="£1m placing at 10p",
        takeaway="£1m placing at 10p. Use of proceeds disclosed. No earnings guidance change.",
        key_facts=[
            KeyFact(label="Gross proceeds", metric="gross proceeds", value="£1m", basis="reported")
        ],
    )
    decision = decide_consistency_review(current_announcement, current_note)
    assert decision.requires_review
    assert any("complex event type: Fundraising" == reason for reason in decision.reasons)


def test_results_guidance_comparators_and_weak_evidence_all_escalate() -> None:
    results_decision = decide_consistency_review(
        announcement(title="Final Results", rns_type="Results & trading"),
        note(rns_type="Results & trading"),
    )
    assert results_decision.requires_review
    assert any("financial results" in reason for reason in results_decision.reasons)

    guidance_note = note(
        guidance_events=[
            GuidanceEvent(
                metric="revenue",
                period="FY27",
                value="£20m",
                status="issued",
            )
        ]
    )
    guidance_decision = decide_consistency_review(announcement(), guidance_note)
    assert guidance_decision.requires_review
    assert any("guidance was issued or changed" in reason for reason in guidance_decision.reasons)

    comparator_note = note(
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                value="£8m",
                basis="reported",
                comparator="Prior disclosure",
                comparator_type="prior-disclosure",
                comparator_source_id="prior-1",
                previous_value="£10m",
            )
        ]
    )
    comparator_decision = decide_consistency_review(
        announcement(),
        comparator_note,
        prior_context=[{"source_id": "prior-1", "published_at": "2026-08-01T07:00:00+00:00"}],
    )
    assert comparator_decision.requires_review
    assert any("comparison" in reason for reason in comparator_decision.reasons)

    partial_decision = decide_consistency_review(
        announcement(evidence_status="partial"),
        note(),
    )
    assert partial_decision.requires_review
    assert any("evidence status is partial" in reason for reason in partial_decision.reasons)

    low_confidence = decide_consistency_review(
        announcement(),
        note(confidence=0.70),
    )
    assert low_confidence.requires_review
    assert any("confidence" in reason for reason in low_confidence.reasons)


def test_guardrail_sensitive_source_cannot_take_single_pass_shortcut() -> None:
    current_announcement = announcement(
        title="Financing Update",
        text=(
            "The company breached its leverage covenant and obtained a waiver. "
            "The facility remains fully drawn."
        ),
        rns_type="Funding & solvency",
    )
    current_note = note(
        rns_type="Other",
        headline="Financing update",
        takeaway="Financing update published. No earnings guidance change disclosed.",
        key_facts=[KeyFact(label="Facility", metric="facility", value="Fully drawn", basis="reported")],
    )
    decision = decide_consistency_review(current_announcement, current_note)
    assert decision.requires_review
    assert any("guardrail" in reason or "high-risk" in reason for reason in decision.reasons)


class StubResponses:
    def __init__(self, outputs: list[AnalystNote]) -> None:
        self.outputs = list(outputs)
        self.calls = 0

    def parse(self, **_kwargs):
        self.calls += 1
        if not self.outputs:
            raise AssertionError("unexpected extra model call")
        return SimpleNamespace(output_parsed=self.outputs.pop(0))


class StubClient:
    def __init__(self, outputs: list[AnalystNote]) -> None:
        self.responses = StubResponses(outputs)


def engine_with(outputs: list[AnalystNote]) -> OpenAIAnalystEngine:
    engine = object.__new__(OpenAIAnalystEngine)
    engine.client = StubClient(outputs)
    engine.model_name = "stub-model"
    engine.max_output_tokens = 12_000
    engine.system_prompt = "system"
    engine.review_prompt = "review"
    engine.initial_analysis_calls = 0
    engine.consistency_review_calls = 0
    engine.last_review_decision = None
    return engine


def test_engine_actually_skips_second_model_call_for_safe_draft() -> None:
    engine = engine_with([note()])
    output = engine.analyse(announcement(), [])

    assert output.source_id == "routing-1"
    assert engine.client.responses.calls == 1
    assert engine.last_review_decision is not None
    assert engine.last_review_decision.mode == "single-pass"
    assert engine.model_call_stats() == {
        "initial_calls": 1,
        "review_calls": 0,
        "reviews_avoided": 1,
        "total_calls": 1,
    }


def test_engine_keeps_second_model_call_for_material_draft() -> None:
    material = note(
        impact_colour="green",
        impact_score=3,
        impact_level="high",
        impact_rationale="The contract is material to current trading.",
        impact_drivers=[
            ImpactDriver(
                dimension="earnings",
                direction="favourable",
                significance=3,
                rationale="The contract is material to current trading.",
            )
        ],
    )
    engine = engine_with([material, material])
    output = engine.analyse(announcement(), [])

    assert output.source_id == "routing-1"
    assert engine.client.responses.calls == 2
    assert engine.last_review_decision is not None
    assert engine.last_review_decision.requires_review
    assert engine.model_call_stats()["review_calls"] == 1


def test_review_policy_failure_fails_closed_to_second_pass(monkeypatch) -> None:
    engine = engine_with([note(), note()])

    def explode(*_args, **_kwargs):
        raise RuntimeError("policy unavailable")

    monkeypatch.setattr("analyst.analyzer.decide_consistency_review", explode)
    engine.analyse(announcement(), [])

    assert engine.client.responses.calls == 2
    assert engine.last_review_decision is not None
    assert engine.last_review_decision.requires_review
    assert "failed closed" in engine.last_review_decision.reasons[0]
