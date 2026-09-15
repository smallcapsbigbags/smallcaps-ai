"""Paste-only evidence contract. Legacy ingestion/storage schemas stay unchanged."""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from analyst.models import AnalystNote, KeyFact, StrictModel, impact_level_from_score

EVIDENCE_VERSION = 'paste-evidence-3'
Assertion = Literal['actual','expected','proposed','conditional','calculated','not-disclosed','source-warning']


class CalculationOperand(StrictModel):
    value: str
    quote: str = Field(min_length=8, max_length=1600)


class EvidenceCalculation(StrictModel):
    operation: Literal['percent-change','ratio','difference','sum']
    left: CalculationOperand
    right: CalculationOperand
    comparable_basis: str = Field(min_length=8, max_length=400)


class EvidenceFact(KeyFact):
    assertion: Assertion
    evidence_quotes: list[str] = Field(default_factory=list, max_length=6)
    condition_quotes: list[str] = Field(default_factory=list, max_length=6)
    calculation: EvidenceCalculation | None = None


class NarrativeEvidence(StrictModel):
    field: Literal['headline','takeaway','what_changed.today','analyst_view','challenges_case','impact_rationale']
    index: int = Field(ge=0, default=0)
    quotes: list[str] = Field(min_length=1, max_length=6)


class MaterialityEvidence(StrictModel):
    basis: Literal['routine','financial-scale','guidance','balance-sheet','dilution',
                   'transaction','operational-milestone','insufficient-context']
    certainty: Literal['actual','committed','expected','conditional','unquantified']
    horizon: Literal['immediate','near-term','longer-term','unknown']
    scale_known: bool
    amount_fact_index: int | None = None
    denominator_fact_index: int | None = None
    evidence_quotes: list[str] = Field(min_length=1, max_length=6)


class EvidenceAnalystNote(AnalystNote):
    key_facts: list[EvidenceFact] = Field(default_factory=list)
    narrative_evidence: list[NarrativeEvidence] = Field(default_factory=list)
    materiality_evidence: MaterialityEvidence

    @model_validator(mode="after")
    def validate_impact_level(self) -> "EvidenceAnalystNote":
        # impact_score is the judgement; impact_level is only a legacy display
        # mapping. Derive it rather than rejecting a valid score for an LLM's
        # inconsistent duplicate label. The generic ingestion schema stays strict.
        self.impact_level = impact_level_from_score(self.impact_score)
        return self


PASTE_EVIDENCE_INSTRUCTIONS = '''
PASTE EVIDENCE CONTRACT — applies to this request's EvidenceAnalystNote schema.
Keep the Pass 2B natural writing, card layout and all analyst fields. Evidence metadata
is not reader-facing prose. Do not fill the headline or metric labels with audit jargon.

For every reported/calculated fact, provide short verbatim evidence_quotes from the
pasted document, including relevant row/column headings for tables. Quotes must occur
in the supplied text; whitespace can vary, but words and figures cannot. Never invent
quotes, source identifiers, comparators or units. Prefer a whole supporting sentence
or table row plus its headings to a naked number. Retain source qualifiers and context.
assertion describes the fact, independently of its basis: actual, expected, proposed,
conditional, calculated, not-disclosed or source-warning. A reported expectation has
basis=reported and assertion=expected, not actual. Provide verbatim condition_quotes
for relevant dependencies (development, deployment, approval, financing). Preserve these
conditions in the affected value/label/note and in primary copy or challenges_case.
'Up to' and 'more than' are not exact amounts. Net bank cash is not gross cash or debt-free.
A year-end cash figure is not the current balance after a subsequent acquisition payment.
For not-disclosed facts, do not invent evidence; empty evidence_quotes is allowed only
for a disclosure gap or source warning. Absence from a paste is not proof about the full RNS.

For calculated facts use a calculation with two quoted operands, a compatible-basis
explanation and one supported operation: percent-change, ratio (as a percentage),
difference or sum. Keep inputs and method in the visible fact note. No free-form formulas.
Do not compare different currencies, adjusted/statutory bases, annual/lifetime values,
or derive cash runway without a disclosed, comparable cash burn figure. Omit unsupported
arithmetic rather than manufacture a calculation. Reporting source percentages is fine.

Provide narrative_evidence for headline, takeaway, what_changed.today, analyst_view,
impact_rationale, and each challenges_case item (index 0 for scalar fields; zero-based
index for challenges_case). These are source supports, not proof of an interpretation.
All figures in prose must occur in those quotes or in an independently validated calculated
fact. Qualify expectations in every affected claim; a caveat elsewhere cannot repair a
false headline. Useful short passages suffice. Do not copy the entire announcement.

MATERIALITY — use the same 1–5 public rubric, separately from direction:
1 Routine: administrative/repeated information with little new investment relevance.
2 Minor: limited incremental development; financial or strategic effect looks small.
3 Material: meaningful commercial/financial/strategic change, including a credible but
  conditional programme. Be explicit when group-scale financial significance is unknown.
4 High: substantial disclosed earnings, funding, dilution, transaction or key operational
  change, supported by evidence. A famous customer or upbeat adjective is not sufficient.
5 Critical: fundamental ownership/survival or comparable decisive change, not mere novelty.
Store the existing internal impact_level mapping for compatibility (3/4 both 'high'); the
public label for 3 remains Material, not High. Do not use the old 'Medium' label to score.
Provide materiality_evidence with basis, certainty, horizon and quotes. A numeric scale
claim requires scale_known=true and the amount and denominator fact indexes, with the
same currency and comparable annual periods. Without these, scale_known=false. Never
invent group revenue, market cap or margin. A missing denominator does NOT make an
important event immaterial, and conditionality does NOT reduce a survival risk.
The rationale is a short evidence-based explanation, not a price prediction. Do not
infer guidance upgrades from management confidence; require an explicit upgrade or a
valid guidance comparator in the pasted text.
'''
