# Smallcaps.ai Jobs UX Direction — Pass 0

**Date:** 23 August 2026  
**Baseline commit:** `3103d7b6d6307f9bb9c98b9e446eabd05aa59035`  
**Working branch:** `ux/jobs-pass-0`

## Objective

Pass 0 establishes the safety, visual baseline and product rules for the final customer-facing refinement. It deliberately does **not** redesign the Feed, change the database schema or alter the Analyst 3.1 reasoning system.

The product promise is:

> **Tell me what changed. Prove it. Explain what it means.**

The common hierarchy across the public product is:

> **Verdict → Evidence → Interpretation → Depth**

## One job per surface

| Surface | Investor question | Target comprehension time |
|---|---|---:|
| Feed | What deserves my attention? | 5–10 seconds |
| Analyst Note | What happened, why does it matter and what should I monitor? | 1–2 minutes |
| Company Intelligence | How is the investment case developing over time? | 5–10 minutes |

## Architecture freeze

The Jobs UX programme is a presentation and content-design refinement over the existing production architecture.

Until a real defect proves otherwise, the following are frozen:

- PostgreSQL schema and versioned analyst-run model;
- Investegate discovery and ingestion behaviour;
- publication-safety and owner-review rules;
- point-in-time Company Memory construction;
- Analyst version `aim-intelligence-analyst-3.1`;
- prompt version `analyst-engine-3.1-sector-intelligence`;
- Feed, Analyst Note and Company Intelligence read-model boundaries;
- Railway topology and schedules.

Pass 1 must use the fields already available to the customer product: headline, takeaway, key facts, impact rationale, analyst view, source links, price reaction and company history. No schema migration is authorised for the Feed refactor.

## Semantic impact language

Internal colour tokens remain useful for deterministic styling and storage. They must not be exposed as investor-facing meaning in the final interface.

| Internal token | Public meaning |
|---|---|
| `red` | **ADVERSE** |
| `amber` | **MIXED** |
| `green` | **FAVOURABLE** |
| `grey` + low impact | **ROUTINE** |
| `grey` + medium/high/critical impact | **NEUTRAL** |

Target public examples:

- `CRITICAL · ADVERSE`
- `HIGH · MIXED`
- `MEDIUM · FAVOURABLE`
- `LOW · ROUTINE`

The colour dot remains a redundant visual cue; the words carry the accessible meaning.

## Feed acceptance gate for Pass 1

A Feed item is not complete until all of the following are true:

- [ ] A normal AIM investor can identify the event outcome in one read.
- [ ] The verdict is the first dominant line after quiet company metadata.
- [ ] The takeaway adds what happened and why it matters without repeating the verdict.
- [ ] Up to three decision-useful evidence points sit directly beneath the takeaway.
- [ ] Reported evidence is labelled once as a section, not repeated beneath every fact.
- [ ] Calculated evidence remains explicitly labelled as a Smallcaps.ai calculation.
- [ ] Narrative evidence uses the primary sans-serif typeface; monospace is reserved for tickers and numerical data.
- [ ] Public impact language uses adverse, mixed, favourable, neutral or routine—not red, amber, green or grey.
- [ ] The fallback announcement type `Other` is not displayed.
- [ ] There is one visually dominant action: `Read analysis →`.
- [ ] Company, original RNS and watchlist controls are secondary and unambiguous.
- [ ] Routine records remain accessible without dominating material announcements.
- [ ] The original RNS remains one direct action away.
- [ ] The primary mobile action has a minimum target height of approximately 44 pixels.
- [ ] No page-level horizontal overflow occurs at 390 pixels.
- [ ] Keyboard focus remains visibly present.
- [ ] All database and RNS text remains HTML-escaped.

## Safety baseline

Pass 0 closes the public error-path defect before visual work begins:

1. Every unexpected public-web exception receives a short `WEB-XXXXXXXX` incident reference.
2. The full exception and traceback are written to application logs with the same reference.
3. The customer sees only the safe service message and incident reference.
4. The reference is escaped before rendering.
5. The public error handler cannot itself fail because of a signature mismatch.

## Visual baseline

The existing `launch-visual-audit` GitHub Actions journey is the approved **before** baseline for this programme. The pull request for this pass must complete the workflow and retain its `smallcaps-launch-visual-audit` artifact, containing:

1. private-beta desktop;
2. Feed desktop;
3. Analyst Note desktop;
4. Company Intelligence desktop;
5. Feed mobile at 390 × 844;
6. Analyst Note mobile at 390 × 844.

Pass 0 intentionally makes no customer-facing Feed hierarchy change, so these screenshots remain the valid pre-refactor reference. Pass 1 screenshots will be assessed against this baseline rather than against memory or subjective preference.

## Pass 0 completion criteria

Pass 0 is complete when:

- the public error path is repaired and covered by tests;
- the semantic impact-label mapping is implemented and covered by tests;
- the full automated test workflow succeeds;
- the visual audit succeeds and its six-image artifact is retained;
- this product contract is merged before the Feed refactor begins.

## Pass 1 entry rule

Pass 1 may change shared presentation components and the Feed only. It must not start the Analyst Note or Company Intelligence redesign until real Trellus, Gamma and Springfield records demonstrate that the revised Feed meets the acceptance gate above.
