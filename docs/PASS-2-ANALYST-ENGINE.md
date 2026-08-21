# Pass 2 — Analyst Engine 2.0

## Objective

Convert the Pass 1 structured-analysis foundation into the definitive Smallcaps.ai equity-analysis contract.

## Locked method

The engine uses one structured inference call per investment-relevant announcement:

```text
source evidence
  → relevant point-in-time company context
  → EXTRACT
  → VERIFY
  → RANK
  → COMPARE
  → CHALLENGE
  → INTERPRET
  → SCORE
  → WRITE
  → deterministic guardrails
  → deterministic quality gate
  → versioned PostgreSQL
```

## Core output

- Impact colour, score and public level;
- explicit Impact rationale;
- structured Impact drivers;
- analytical headline and takeaway;
- key facts with basis, period, comparator and source identity;
- new versus reiterated information;
- Before → Today → Read-through;
- Analyst View;
- Supports / Challenges;
- Guidance events;
- management claims;
- What to Watch;
- disclosure assessment;
- source references, warnings and confidence.

## Investor disciplines

The prompt enforces:

- “versus what?” before direction;
- guidance before management adjectives;
- cash conversion alongside profit;
- financing source alongside cash improvement;
- dilution and runway alongside fundraising proceeds;
- leverage and integration alongside acquisition growth;
- relative scale and missing economics for contracts;
- net economic exposure for ownership and director dealings;
- mechanical takeover completion versus distressed delisting;
- technical milestones versus commercial economics.

## Publication quality

`analyst.quality.assess_analysis_quality()` identifies:

- missing/partial evidence;
- unaddressed guardrail failures;
- unsupported established coverage;
- low confidence;
- missing high-impact rationale/drivers;
- absent key facts;
- missing source references;
- insufficient disclosure;
- source inconsistencies.

Blocked output is not written to the current research record.

## Benchmark suite

`benchmarks/cases.json` contains 16 canonical difficult-announcement cases covering:

- profit warning;
- upgrade/deleveraging;
- vague contract;
- rescue placing;
- leveraged acquisition;
- open-market director purchase;
- tax-cover sale;
- going concern/covenant waiver;
- abrupt CEO departure;
- profit growth with cash deterioration;
- firm takeover offer;
- scheme effectiveness/cancellation;
- clinical milestone with no economics;
- material customer loss;
- routine voting rights;
- LTIP dilution.

Run the live benchmark with:

```bash
python -m jobs.run_analyst_benchmarks
```

It requires `OPENAI_API_KEY`. CI validates the benchmark definitions and evaluator without consuming API credits.

## Completion gate

Pass 2 is code-complete when:

1. all automated tests pass;
2. unavailable evidence is retryable rather than published;
3. guardrail failures block persistence;
4. Analyst Engine 2.0 is the default prompt/version;
5. structured new/reiterated/comparator/Impact fields persist correctly;
6. the benchmark harness loads all canonical cases.

A credentialled live benchmark remains an operational validation step before public launch.
