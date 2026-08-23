# Smallcaps.ai Jobs UX — Pass 1 Final Acceptance

**Date:** 23 August 2026

Pass 1 is complete when the AIM Feed behaves as a scan-first investor product rather than a database view.

## Final hierarchy

> **Verdict → Evidence → Smallcaps.ai view → Depth**

The Feed answers one question: **what deserves my attention?**

## Final editorial rules

- The displayed verdict must lead with the investor outcome when the stored analysis already contains enough evidence to support a shorter formulation.
- The presentation adapter may simplify wording only for high-confidence event patterns; otherwise the stored analyst headline is preserved unchanged.
- Evidence labels use short noun phrases where a deterministic rewrite does not alter meaning.
- Ambiguous one-word evidence values may be expanded only when the existing fact label and value jointly support the clearer wording.
- Comparators are shown only when they add real prior-state information. `Not disclosed`, `No … disclosed`, coverage-building text and other non-information comparators are suppressed.
- The section label is **Evidence from the RNS**. Calculated facts remain explicitly labelled **Smallcaps.ai calculation**.
- The Feed interpretation is deliberately shorter than the full Analyst Note. Event-specific high-confidence summaries may state the investment consequence directly; otherwise the concise impact rationale is preferred and capped for scanability.
- Trellus-style administration/no-recovery disclosures resolve to **Administration imminent; no shareholder return expected** and a concise **Thesis broken** interpretation when the stored evidence supports both conclusions.
- Preliminary possible-offer disclosures with no disclosed offer terms resolve to **Formal takeover interest emerges; terms remain unknown**.
- Known offer terms prevent the takeover presentation adapter from replacing the stored headline.

## Final visual rules

- Semantic impact language remains investor-facing: `CRITICAL · ADVERSE`, `HIGH · MIXED`, `HIGH · FAVOURABLE`, etc.
- Fallback type `Other` is hidden.
- Narrative evidence uses sans-serif; compact numerical evidence may use monospace.
- There is one dominant action: **Read analysis →**.
- Company, Original RNS and Watch are quiet secondary actions grouped with the primary action rather than stretched across the full desktop width.
- Routine score-1 announcements remain accessible but are demoted under the default impact sort.
- Mobile retains a full-width primary action of at least 44px and one-column evidence.

## Acceptance set

Pass 1 must be tested against:

1. **Trellus Health** — critical adverse administration / no-recovery event.
2. **Gamma Communications** — high mixed preliminary takeover process with no offer terms.
3. **Springfield Properties** — high favourable capital-allocation event where the stored verdict is already useful and must not be over-edited.

The adapter is intentionally conservative. It is a presentation layer, not a replacement analyst engine, and it does not mutate stored research or the PostgreSQL schema.
