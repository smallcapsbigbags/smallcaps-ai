# Phase 3 Pass 2 — Live Company Validation

## Purpose

Pass 1 built Company Memory. Pass 2 proves that the same context construction used in production remains trustworthy as real company histories accumulate.

The validation question is:

> At every RNS date, did Smallcaps.ai see all eligible earlier company records, no current or future record, traceable comparators, and a compact history relevant to the new announcement?

This pass starts with Springfield Properties and then adds covered companies with deeper and more varied RNS histories.

## What this pass adds

### One production context builder

`analyst.company_context.build_company_analysis_context` is now the single path for:

- filtering strictly earlier records;
- rejecting the current RNS, future RNSs, duplicates and another ticker's records;
- building the deterministic Company Memory snapshot;
- selecting up to seven exact earlier RNS records;
- separating reported company disclosure, Smallcaps.ai calculations and prior Smallcaps.ai interpretation;
- returning the deterministic coverage status.

The live pipeline and validation job use this same function. The validator therefore cannot pass by exercising a different implementation from production.

### Chronological reconstruction

`analyst.company_validation.validate_company_timeline` rebuilds the context that each publishable RNS would have received at its publication time. It checks:

- the eligible source IDs equal the strictly earlier company timeline;
- the current RNS cannot enter its own context;
- later RNSs cannot leak backwards;
- selected prior records remain chronological and within the context limit;
- memory announcement counts and coverage status are deterministic;
- `generated_before` and the latest covered record are genuinely earlier than the current RNS;
- fact and guidance comparator source IDs are present in eligible history or explicitly restated by the current RNS;
- stable management claim keys do not silently re-open after a resolved outcome;
- structured memory produces useful KPI, guidance or claim yield as coverage deepens.

This reconstruction makes no model call.

### Live database candidate selection

`database.company_validation.CompanyValidationRepository` ranks covered companies using:

- number of publishable RNS records;
- number of different RNS/event types;
- coverage span;
- recency;
- explicit priority for Springfield.

The validator reads the existing versioned PostgreSQL record. It creates no second research database and does not alter public analyses.

### Zero-token validation job

Run:

```bash
python -m jobs.validate_company_memory_live \
  --tickers SPR \
  --auto 3 \
  --minimum-history 2 \
  --output company-memory-live-validation.json
```

The job validates Springfield plus up to three additional covered companies with sufficiently deep histories. It exits non-zero when:

- a requested company is not covered;
- a company has fewer than the required publishable RNS records;
- any point-in-time reconstruction contains a current/future leak;
- a comparator source is untraceable;
- deterministic coverage or memory counts are inconsistent;
- no company can be validated.

`railway.company-memory-live.json` is a one-off Railway service configuration. It is not a continuous production worker.

## Cost

The live reconstruction has **zero OpenAI token cost**. It reads PostgreSQL and runs deterministic Python checks.

The separate four-case `run_company_memory_benchmark` remains available when an AI judgement regression is needed. That benchmark should not be rerun merely to inspect database chronology.

## Acceptance gate

Pass 2 is ready to close when:

1. the full automated test suite and PostgreSQL integration tests pass;
2. the production web and ingestion services deploy from the shared context-builder commit;
3. Springfield has at least two publishable records and passes every chronological point;
4. at least two further companies with different event types pass;
5. all stored comparator source IDs are traceable at the date they were used;
6. no current or future RNS enters prior context;
7. any low structured-memory yield is recorded honestly rather than hidden;
8. repeated retrieval/ranking weaknesses are corrected once, in the shared builder, rather than patched company by company.

## Deliberate limits

This pass does not:

- manufacture historical RNSs;
- run a full AIM backfill;
- use broker consensus;
- rewrite existing analyses merely to improve Company Intelligence density;
- call OpenAI during deterministic live validation;
- treat thin history as established coverage.

Selective historical ingestion for a small number of validation companies may be considered separately when the source evidence and data rights are appropriate. It must use the normal evidence and quality gates rather than synthetic fixtures.
