from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from analyst.classification import canonical_rns_type
from analyst.guardrails import guardrail_warnings
from analyst.intelligence import AnalystIntelligenceBundle
from analyst.models import AnalystNote, AnnouncementInput
from analyst.quality import assess_analysis_quality

ReviewMode = Literal["single-pass", "review"]

REVIEW_POLICY_VERSION = "facts-no-fluff-review-routing-1.0"

# These event families are structurally complex enough that a second evidence-bound
# consistency pass is cheap insurance even when the first draft looks low impact.
_ALWAYS_REVIEW_TYPES = {
    "Funding & solvency",
    "Fundraising",
    "Acquisition",
    "Disposal",
    "Takeover",
    "Corporate",
    "Remuneration",
}

_RESULTS_TITLE_RE = re.compile(
    r"\b(?:final|interim|annual|half[- ]year|full[- ]year) results\b",
    re.IGNORECASE,
)
_HIGH_RISK_SOURCE_RE = re.compile(
    r"(?:"
    r"\bprofit warning\b|"
    r"\bmaterial uncertainty\b.{0,100}\bgoing concern\b|"
    r"\bgoing concern\b.{0,100}\bmaterial uncertainty\b|"
    r"\bcovenants?\b.{0,100}\b(?:breach|breached|waiver|non[- ]compliance)\b|"
    r"\binsufficient working capital\b|"
    r"\b(?:repayable|payable|due) on demand\b|"
    r"\b(?:requires?|will require|needs?|will need) (?:additional |further )?(?:funding|finance|capital)\b|"
    r"\b(?:largest|major|key|material) customer\b.{0,120}\b(?:lost|terminated|termination|cancelled)\b|"
    r"\bcontract\b.{0,120}\b(?:terminated|termination|cancelled|cancellation)\b|"
    r"\b(?:ceo|cfo|chief executive|chief financial officer)\b.{0,120}\b(?:resign|resigned|resignation|depart|departure|left|leave|leaving)\b|"
    r"\b(?:resign|resigned|resignation|depart|departure|left|leave|leaving)\b.{0,120}\b(?:ceo|cfo|chief executive|chief financial officer)\b|"
    r"\brule\s*9\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_MATERIAL_GUIDANCE_STATUSES = {
    "issued",
    "upgraded",
    "downgraded",
    "withdrawn",
    "delivered",
    "missed",
}


@dataclass(frozen=True)
class ReviewDecision:
    mode: ReviewMode
    reasons: tuple[str, ...]
    policy_version: str = REVIEW_POLICY_VERSION

    @property
    def requires_review(self) -> bool:
        return self.mode == "review"


def _has_supported_comparison(note: AnalystNote) -> bool:
    for fact in note.key_facts:
        if (
            fact.comparator_type != "none"
            or fact.comparator_source_id.strip()
            or fact.previous_value.strip()
        ):
            return True
    for event in note.guidance_events:
        if event.previous_source_id.strip() or event.previous_value.strip():
            return True
    return any(claim.status != "open" for claim in note.management_claims)


def _has_material_guidance_change(note: AnalystNote) -> bool:
    return any(event.status in _MATERIAL_GUIDANCE_STATUSES for event in note.guidance_events)


def _normalise_context(
    prior_context: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [dict(record) for record in prior_context]


def decide_consistency_review(
    announcement: AnnouncementInput,
    draft: AnalystNote,
    *,
    prior_context: Sequence[Mapping[str, object]] = (),
    intelligence: AnalystIntelligenceBundle | None = None,
) -> ReviewDecision:
    """Choose whether the expensive second analyst pass is genuinely warranted.

    The policy is intentionally loss-averse. A single pass is allowed only for a
    low-materiality, high-confidence draft that passes deterministic quality and
    guardrail checks and contains no complex transaction, supported comparison or
    high-risk source language. Any uncertainty falls back to review.
    """

    reasons: list[str] = []
    context = _normalise_context(prior_context)
    event_type = canonical_rns_type(announcement, draft.rns_type)

    if event_type in _ALWAYS_REVIEW_TYPES:
        reasons.append(f"complex event type: {event_type}")

    if event_type == "Results & trading" and _RESULTS_TITLE_RE.search(announcement.title):
        reasons.append("financial results require a second consistency pass")

    if draft.impact_score >= 3:
        reasons.append(f"materiality {draft.impact_score}/5")

    if announcement.evidence_status != "complete":
        reasons.append(f"evidence status is {announcement.evidence_status}")

    if draft.confidence < 0.85:
        reasons.append(f"first-pass confidence is {draft.confidence:.2f}")

    if _has_supported_comparison(draft):
        reasons.append("draft uses prior-period or prior-disclosure comparison")

    if _has_material_guidance_change(draft):
        reasons.append("guidance was issued or changed")

    if _HIGH_RISK_SOURCE_RE.search(announcement.text):
        reasons.append("source contains a high-risk review trigger")

    if intelligence is not None and any(
        finding.severity == "review" for finding in intelligence.findings
    ):
        reasons.append("deterministic analyst intelligence found an unresolved review issue")

    guardrails = guardrail_warnings(
        announcement,
        draft,
        prior_context=context,
    )
    if guardrails:
        reasons.append("first-pass guardrail check found an issue")

    quality = assess_analysis_quality(
        announcement,
        draft,
        prior_context=context,
    )
    if quality.status != "publishable":
        reasons.append(f"first-pass quality status is {quality.status}")

    reasons = list(dict.fromkeys(reasons))
    if reasons:
        return ReviewDecision(mode="review", reasons=tuple(reasons))
    return ReviewDecision(
        mode="single-pass",
        reasons=(
            "low-materiality, high-confidence draft passed deterministic guardrails and quality checks",
        ),
    )
