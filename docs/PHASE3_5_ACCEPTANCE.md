# Phase 3.5 — Analyst 3.1 Acceptance Record

## Scope under test

This acceptance record covers the Analyst 3.1 sector KPI and contradiction layer introduced on `phase3/analyst-intelligence-layer`.

The release adds:

- deterministic company-archetype and KPI profiles;
- sector-specific relationship checks;
- a post-draft contradiction detector;
- final consistency-review integration;
- fail-safe publication checks for unresolved material findings;
- no new OpenAI call and no new database table.

## Deterministic acceptance — passed

GitHub Actions ran the complete repository suite with PostgreSQL 16.

### Signal benchmark

`benchmarks/analyst_intelligence_cases.json`

Result: **11/11 passed**.

The locked cases cover:

- acquisition-led growth with weaker margin and debt;
- recruiter net fee income being omitted;
- life-sciences funding risk;
- lender growth with weaker credit indicators;
- ARR growth with weaker cash quality;
- mining production with higher AISC;
- retail sales with margin and inventory pressure;
- backlog growth with weaker current profit;
- housebuilding volume with weaker margin;
- maintained guidance with higher debt;
- a balanced-growth no-false-positive control.

### Additional control benchmark

`benchmarks/analyst_intelligence_controls.json`

Result: **6/6 passed**.

The controls cover:

- oil-and-gas production with higher unit cost;
- a property disposal with improving leverage and no false contradiction;
- recruiter NFI correctly prioritised;
- a life-sciences milestone explicitly funded through the next event;
- lender growth with improving credit quality;
- efficient software ARR growth with rising cash.

### Repository suite

Result: **118 tests passed**.

The suite includes:

- Python compilation;
- SQLite and PostgreSQL round trips;
- Company Memory no-look-ahead and provenance checks;
- Company Intelligence rendering and escaping;
- Analyst prompt contracts;
- both Analyst Intelligence benchmark files and all Railway JSON files;
- existing ingestion, market-reaction and product tests.

## Deterministic release gates

| Gate | Result |
|---|---|
| Every signal case infers the expected analytical profile | Passed |
| Every required relationship finding is detected | Passed |
| Every forbidden false positive is absent | Passed |
| H1/FY, unit, currency and reported/calculated comparability remains enforced | Passed |
| Raw KeyFact labels cannot falsely satisfy an analytical finding | Passed |
| Explicit funding sufficiency does not create a funding warning | Passed |
| Unresolved review-level findings prevent automatic publication | Passed |
| No additional model call is introduced | Passed |
| Existing PostgreSQL and Company Memory tests remain green | Passed |

## Live model gate — pending

The deterministic layer is ready, but Analyst 3.1 changes the instructions and payload supplied to the live OpenAI Analyst Engine. It must therefore pass a live regression before production merge.

The required sequence is:

1. run the locked hard-case preflight using `railway.analyst31-preflight.json`;
2. inspect every non-publishable or materially changed result;
3. run the full 20-case gold-standard benchmark using `railway.benchmark.json`;
4. run the four-case Company Memory benchmark;
5. merge to `main` only if the existing factual, Impact, plain-English and point-in-time gates remain satisfied.

The preflight config runs:

```text
python -u -m jobs.run_gold_standard_benchmark \
  --case-set benchmarks/preflight_case_set.json \
  --output analyst-31-preflight-results.json
```

The full benchmark config runs:

```text
python -u -m jobs.run_gold_standard_benchmark \
  --case-set benchmarks/real_case_set.json \
  --output gold-standard-results.json
```

## Production decision

**Current status: deterministic acceptance passed; production merge withheld pending the live OpenAI regression.**

This is intentional. The new layer should not be promoted merely because the Python rules work. The final question is whether those rules improve the real Analyst Note without increasing false warnings, verbosity, Impact errors or unsupported sector assumptions.
