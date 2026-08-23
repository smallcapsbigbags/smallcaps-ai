# Smallcaps.ai Jobs UX Direction — Pass 4

**Date:** 23 August 2026  
**Base:** Pass 3 production  
**Scope:** Analyst output contract and RNS taxonomy only

## Objective

Make the analytical engine naturally produce content that fits the product hierarchy already implemented in Passes 1–3:

> **Tell me what changed. Prove it. Explain what it means.**

Pass 4 changes the words and classification contract, not the layout.

## Frozen surfaces

The following remain frozen:

- Feed layout and action hierarchy;
- Analyst Note layout and progressive disclosure;
- Company Intelligence layout;
- private-beta entrance;
- PostgreSQL schema;
- ingestion discovery/evidence source;
- Company Memory logic;
- market-reaction logic;
- Railway topology.

## Editorial contract

The Analyst Engine must now produce Feed-ready public fields without relying on presentation adapters to rescue weak model copy.

### Headline

- normally 6–12 words;
- outcome first;
- investor verdict rather than RNS topic description;
- certainty no stronger than the evidence.

Canonical severe-distress example:

`Administration imminent; no shareholder return expected`

Canonical possible-offer example:

`Formal takeover interest emerges; terms remain unknown`

### Takeaway

- normally two short sentences;
- approximately 45 words or fewer;
- sentence one = what happened;
- sentence two = why it matters;
- no headline repetition.

### First three facts

- decision-useful order;
- labels normally 1–4 words;
- values self-contained;
- no meaningless comparator placeholders;
- reported/calculated provenance preserved.

### Impact rationale

- one sentence;
- approximately 35 words or fewer;
- strongest reason for significance and direction.

### Analyst view

- first sentence states the investment-case consequence;
- normally 2–3 short sentences;
- approximately 90 words or fewer;
- then explain why and what remains to prove.

## Canonical taxonomy

Pass 4 introduces a stable public category set and a dedicated:

`Funding & solvency`

This category covers supported survival/distress events such as administration, insolvency, material going-concern uncertainty, insufficient working capital, covenant breach/waiver caused by stress, rescue financing, funding shortfalls and material refinancing deadlines.

Normal results mentioning debt or the standard going-concern basis must not be misclassified as distress.

Solvency events receive the highest deterministic ingestion priority so they cannot be displaced by less consequential announcements when the daily AI cap is reached.

## Deterministic safety backstops

The taxonomy is normalised before quality checks and persistence. A model-created arbitrary category is not exposed publicly when a canonical category can be determined.

The quality layer now checks for material editorial drift after the second model review:

- very long headlines;
- overlong/multi-sentence takeaways;
- overlong impact rationales;
- overlong analyst views;
- first-three fact labels that are not Feed-ready;
- ambiguous standalone values such as `Filed`.

Small deviations remain informational. Material drift routes a new analysis to owner review rather than silently publishing a weaker product.

## Versioning

New live analysis is versioned as:

- `ANALYSIS_VERSION = aim-intelligence-analyst-3.2`
- `PROMPT_VERSION = analyst-engine-3.2-editorial-contract`

This prevents future 3.2 output being mislabeled as Analyst 3.1.

## Historical records

Pass 4 does **not** mass re-analyse historical RNSs.

Existing records continue to benefit from the Pass 1–3 presentation adapters. The tighter editorial/taxonomy contract applies to newly analysed RNSs and any record that is deliberately re-analysed later for a real analytical reason.

## Acceptance gate

Pass 4 is complete only when:

1. the full repository test suite passes;
2. deterministic intelligence benchmarks pass unchanged;
3. classification tests distinguish real solvency distress from normal going-concern wording;
4. the editorial-contract tests pass;
5. the existing desktop/mobile visual regression suite for Passes 1–3 remains green;
6. Railway deploys `main` with Postgres + smallcaps-ai + AIM Ingestion healthy;
7. AIM Ingestion retains its existing weekday cron schedule.
