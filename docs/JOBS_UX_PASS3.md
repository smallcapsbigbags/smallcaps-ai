# Smallcaps.ai Jobs UX Direction — Pass 3

**Date:** 23 August 2026  
**Base:** Pass 2 production  
**Scope:** Company Intelligence and private-beta entrance only

## Objective

Complete the Jobs-style product hierarchy by giving Company Intelligence one clear job:

> **How is the investment case developing over time?**

The private-beta entrance must make one promise and ask for one action.

Feed and Analyst Note presentation are frozen in this pass. PostgreSQL, ingestion, Company Memory, Analyst 3.1, prompt version and Railway topology are also frozen.

## Company Intelligence contract

### Order

1. Company identity and quiet coverage line.
2. **Current position** — latest verdict, impact and Smallcaps.ai view.
3. **Guidance** — only when current guidance exists.
4. **Metrics that matter** — three highest-ranked comparable series first; remaining series progressively disclosed.
5. **Management promises** — open commitments by default; resolved commitments secondary.
6. **What remains unclear** — only genuine carried-forward disclosure gaps.
7. **RNS timeline** — compact event history with one restrained Read action per row.

### Removed

- system-count cards such as Analysed RNSs, Tracked metrics and Open promises;
- the large blue coverage-building notice;
- empty guidance / metric / promise / disclosure sections;
- repeated full RNS summaries in the timeline;
- two large action buttons beneath every historical RNS.

### Coverage honesty

Coverage status remains visible, but as quiet metadata:

`Coverage since 1 Aug 2026 · 2 analysed RNSs · history still building`

No historical thesis is invented. The Current position is the latest publishable Smallcaps.ai view, not a newly generated cross-RNS recommendation.

### Metrics

The Company Memory engine already ranks metric series by decision usefulness and comparability. Pass 3 uses that deterministic ordering and shows the first three series by default. Directional movement is factual (`Down 24.2% from £24.0m`) and is not labelled good or bad.

### Timeline

The timeline is scan-first: date, useful category, impact signal, verdict, source and one `Read analysis →` action. The first 12 records remain visible; older records move behind `Earlier announcements`.

## Private-beta entrance contract

The entrance is reduced to:

> **Know what changed. See the evidence.**
>
> Every AIM announcement analysed in minutes, with reported facts and Smallcaps.ai judgement kept separate.

Then one password field, one `Enter Smallcaps.ai` action and the research disclaimer.

The old three feature cards are removed from the active product surface.

## Mobile

At 390px:

- Company metrics collapse to one column;
- guidance rows become a two-column information grid with the metric spanning the row;
- current-position actions wrap with the primary action first;
- timeline remains compact with no page-level horizontal overflow;
- the beta entrance remains a single readable message with a full-width access action.

## Acceptance gate

Pass 3 is complete only when:

- full repository tests pass;
- desktop and 390px visual audit pass;
- Feed and Analyst Note Pass 1/2 assertions continue to pass unchanged;
- beta entrance contains one proposition, one input and one action;
- Trellus Company Intelligence shows Current position + compact timeline without system-count cards;
- Springfield Company Intelligence shows Current position, Guidance, three primary metrics, Management promises, What remains unclear and at least two timeline records;
- system-count cards and the large coverage-building banner are absent;
- mobile Springfield metrics render in one column;
- all external source URLs remain validated and untrusted content remains HTML-escaped;
- Railway remains Postgres + smallcaps-ai + AIM Ingestion and all required services are healthy.
