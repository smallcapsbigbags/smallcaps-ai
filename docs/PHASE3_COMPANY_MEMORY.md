# Phase 3 — Company Memory and Company Intelligence

## North Star

A new RNS should not be analysed as if the company has never spoken before.
Smallcaps.ai should be able to answer:

- What did management previously say?
- What changed today?
- Are the disclosed numbers moving in the promised direction?
- Which management claims remain unproven?
- What should the investor measure next?

## Design rules

1. **No expensive historical AI backfill for the MVP.** Memory grows from every RNS already analysed by the live service.
2. **No look-ahead.** A note may only receive company information published before that RNS.
3. **One source of truth.** Company Intelligence reads the existing PostgreSQL facts, guidance, claims and analyst runs. It does not create a second research database.
4. **Provenance remains visible.** Reported, calculated and inferred information cannot be blurred.
5. **Compact context.** Only the latest relevant guidance, recent KPI observations, open promises, balance-sheet facts and prior judgements are passed forward.
6. **The page admits when memory is thin.** One RNS is `building`; two to four are `emerging`; five or more are `established`.

## Phase 3 passes

### Pass 1 — Memory foundation

- deterministic point-in-time memory builder;
- latest guidance and KPI series;
- open management promises;
- balance-sheet lens;
- safe like-for-like calculations;
- compact prior-context payload;
- no-look-ahead and provenance tests.

### Pass 2 — Live company validation

- validate Springfield first;
- inspect two or three further companies with different event types;
- prove that the next RNS sees eligible prior facts and guidance;
- correct only repeated retrieval or ranking failures.

### Pass 3 — Company Intelligence UX

- coverage status;
- current guidance;
- key numbers over time;
- balance sheet and funding;
- promises to test;
- calculated changes;
- RNS impact timeline;
- honest empty/building states.

### Pass 4 — Management delivery record

- mark claims delivered, missed, superseded or still open;
- show the evidence used to change status;
- surface contradictions and changes in wording;
- add a focused benchmark for point-in-time company comparisons.

## Deliberately deferred

- broker consensus and price targets;
- full AIM historical backfill;
- automatically generated valuation models;
- Buy/Sell/Hold recommendations;
- public user accounts and alerts (Phase 4).
