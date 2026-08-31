from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyst.routing_benchmark import (
    RoutingAuditRecord,
    RoutingPairJudgement,
    routing_benchmark_acceptance,
)


def record(case_id: str, **updates) -> RoutingAuditRecord:
    values = {
        "case_id": case_id,
        "decision_mode": "single-pass",
        "decision_reasons": ["low-materiality clean draft"],
        "routed_publishable": True,
        "routed_gold_passed": True,
        "routed_score": 88,
        "routed_factual_grounding": 19,
        "routed_critical_failures": [],
        "routed_impact_alignment": "aligned",
        "routed_impact_colour": "grey",
        "routed_impact_score": 2,
        "shadow_reviewed": True,
        "shadow_publishable": True,
        "shadow_gold_passed": True,
        "shadow_score": 89,
        "shadow_factual_grounding": 19,
        "shadow_impact_colour": "grey",
        "shadow_impact_score": 2,
        "pairwise_acceptable": True,
        "pairwise_material_regressions": [],
    }
    values.update(updates)
    return RoutingAuditRecord(**values)


def test_pairwise_judgement_cannot_hide_a_material_regression() -> None:
    with pytest.raises(ValueError):
        RoutingPairJudgement(
            acceptable_single_pass=True,
            factual_regression=True,
            material_regressions=["Routed note omitted disclosed net debt."],
        )


def test_single_pass_audit_requires_forced_shadow_review() -> None:
    with pytest.raises(ValueError):
        record(
            "missing-shadow",
            shadow_reviewed=False,
            shadow_publishable=None,
            shadow_gold_passed=None,
            shadow_score=None,
            shadow_factual_grounding=None,
            shadow_impact_colour=None,
            shadow_impact_score=None,
            pairwise_acceptable=None,
        )


def test_pass4_acceptance_proves_quality_and_call_savings() -> None:
    records = [
        record("routine-contract"),
        record("technical-update", routed_score=90, shadow_score=91),
        record(
            "profit-warning",
            decision_mode="review",
            decision_reasons=["materiality 5/5"],
            routed_impact_colour="red",
            routed_impact_score=5,
            shadow_reviewed=False,
            shadow_publishable=None,
            shadow_gold_passed=None,
            shadow_score=None,
            shadow_factual_grounding=None,
            shadow_impact_colour=None,
            shadow_impact_score=None,
            pairwise_acceptable=None,
        ),
    ]

    acceptance = routing_benchmark_acceptance(
        records,
        expected_cases=3,
        min_single_pass_cases=2,
    )

    assert acceptance["passed"] is True
    assert acceptance["single_pass_count"] == 2
    assert acceptance["reviewed_count"] == 1
    assert acceptance["baseline_two_pass_analyst_calls"] == 6
    assert acceptance["routed_analyst_calls"] == 4
    assert acceptance["analyst_calls_avoided"] == 2
    assert acceptance["analyst_call_reduction_pct"] == 33.3


def test_pairwise_material_regression_blocks_pass4() -> None:
    acceptance = routing_benchmark_acceptance(
        [
            record(
                "bad-single-pass",
                pairwise_acceptable=False,
                pairwise_material_regressions=[
                    "Forced review restored a material funding disclosure."
                ],
            )
        ],
        expected_cases=1,
        min_single_pass_cases=1,
    )

    assert acceptance["passed"] is False
    assert "bad-single-pass" in acceptance["regression_cases"]


def test_material_impact_drift_blocks_single_pass() -> None:
    acceptance = routing_benchmark_acceptance(
        [
            record(
                "impact-drift",
                routed_impact_colour="grey",
                routed_impact_score=1,
                shadow_impact_colour="amber",
                shadow_impact_score=3,
            )
        ],
        expected_cases=1,
        min_single_pass_cases=1,
    )

    reasons = acceptance["regression_cases"]["impact-drift"]
    assert acceptance["passed"] is False
    assert any("impact direction/colour" in item for item in reasons)
    assert any("materiality" in item for item in reasons)


def test_gold_score_and_factual_grounding_regressions_are_bounded() -> None:
    acceptance = routing_benchmark_acceptance(
        [
            record(
                "quality-drift",
                routed_score=84,
                shadow_score=90,
                routed_factual_grounding=17,
                shadow_factual_grounding=20,
            )
        ],
        expected_cases=1,
        min_single_pass_cases=1,
    )

    reasons = acceptance["regression_cases"]["quality-drift"]
    assert acceptance["passed"] is False
    assert any("3 points" in item for item in reasons)
    assert any("factual grounding" in item for item in reasons)


def test_pass4_case_set_is_locked_unique_and_mixes_cost_cases_with_risk_controls() -> None:
    case_ids = json.loads(
        Path("benchmarks/pass4_routing_case_set.json").read_text(encoding="utf-8")
    )
    assert len(case_ids) == 12
    assert len(case_ids) == len(set(case_ids))

    # Low/moderate cases exercise the potential one-pass route.
    for required in (
        "gms-contract-extension-2026-08-17",
        "eee-drill-update-2026-08-19",
        "time-out-trading-2026-08-18",
    ):
        assert required in case_ids

    # High-risk controls prove the router still spends the second call where it matters.
    for required in (
        "rbn-interims-warning-2026-08-20",
        "time-takeover-2026-08-17",
        "atm-strategic-funding-2026-08-17",
    ):
        assert required in case_ids
