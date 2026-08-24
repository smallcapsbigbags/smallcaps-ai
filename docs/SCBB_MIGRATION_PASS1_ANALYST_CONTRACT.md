# SmallcapsBigBags Migration — Pass 1: Analyst Contract

**Baseline:** `dc73dbd59a11db48fd695990058cb4856e70d166`  
**Branch:** `analyst/scbb-monitoring-pass1`

## Objective

Make every new Smallcaps.ai analysis naturally populate the existing SmallcapsBigBags Analyst Monitoring Sheet before any API or frontend migration begins.

The exact visual port is deliberately outside this pass. Pass 1 changes the analyst's final editorial output, not the Streamlit UI, PostgreSQL schema, ingestion engine or Company Memory architecture.

## Source of truth

The SmallcapsBigBags research methodology governs the final monitoring output:

> **AI View can be selective; facts cannot be selective.**

The analyst operates as an experienced, sceptical UK small-cap equity analyst maintaining a private monitoring sheet for a professional investor.

## Monitoring-sheet contract

| Monitoring column | Smallcaps.ai source |
|---|---|
| Signal | `impact_colour` → GREEN / AMBER / RED / NO COLOUR |
| What Changed | `what_changed.today` |
| AI View | `analyst_view`, maximum 50 words |
| Outlook | derived from genuine `guidance_events` |
| Balance Sheet | current reported facts; carried context later comes from Company Memory |
| Impact | `impact_score`, independently calibrated 1–5 |

## Required analyst behaviour

1. Extract all mandatory facts and preserve reported/calculated/not-disclosed/source-warning provenance.
2. Compare today with the strongest supported previous company disclosure.
3. Make `what_changed.today` the single most decision-useful delta.
4. Run the internal “What's the catch?” challenge without manufacturing criticism.
5. Derive Outlook only from genuine guidance events.
6. Retain current cash/debt/liquidity facts with dates when disclosed.
7. Write a judgement-led AI View of no more than 50 words.
8. Route output needing editorial rescue to owner review.

## Pass 1 acceptance cases

- Maintained guidance with lower net debt.
- Preliminary takeover with terms still unknown.
- Administration / no expected shareholder recovery.
- Contract with committed and optional value.
- Routine remuneration update.
- Announcement that is confirmation rather than new information.
- Balance-sheet impact supported by a dated fact.
- Carried-forward balance-sheet context retaining its reporting period.

## Frozen in this pass

- database schema;
- current public Streamlit layout;
- AIM ingestion and evidence retrieval;
- canonical RNS taxonomy;
- Company Memory storage;
- publication-safety architecture;
- market-reaction system;
- historical analyses.

Existing records are not mass re-analysed. The first eligible live announcement after deployment becomes the first Analyst 3.3 monitoring-sheet record.

## Version

- Analysis: `aim-intelligence-analyst-3.3`
- Prompt: `analyst-engine-3.3-scbb-monitoring-sheet`

## Exit criteria

Pass 1 is complete when:

- the monitoring-sheet prompt is the final editorial contract;
- AI View over 50 words routes to review;
- missing/generic What Changed routes to review;
- balance-sheet impact requires supporting evidence;
- Signal and Outlook can be derived deterministically;
- all existing tests and analyst benchmarks pass;
- production configuration points at the new prompt version;
- no historical re-analysis or frontend change occurs.
