# SmallcapsBigBags Migration — Pass 4: Company Intelligence

**Baseline:** `8814024538a390aaaf5e92da0fe3036777a4779e`  
**Branch:** `frontend/scbb-company-pass4`

## Objective

Rebuild Company Intelligence in the same near-black, cyan, dense analyst-monitoring language as the SmallcapsBigBags Research page and the Pass 3 AIM RNS feed.

Pass 4 does not change ingestion, Analyst 3.3, Company Memory construction, publication safety, PostgreSQL or the Railway service topology.

## Investor question

The company page should answer:

> How is the investment case developing through successive RNS announcements?

The visible hierarchy is:

1. current view;
2. outlook and guidance;
3. metrics that matter;
4. management promises;
5. what remains unclear;
6. RNS history.

## Company sheet contract

Schema version: `scbb-company-v1`

`GET /api/v1/company/{ticker}` composes only current, publishable records from:

- the latest `scbb-monitoring-v1` Analyst Note;
- deterministic Company Memory;
- public company RNS history;
- stored event-day market reaction;
- original source provenance.

The frontend does not reconstruct investment analysis in JavaScript.

## Current view

The page leads with the latest publication-safe verdict, What Changed and the full stored AI View. It also exposes:

- Signal;
- Outlook;
- market reaction;
- balance-sheet context;
- Impact 1–5;
- original RNS provenance;
- the complete Analyst Note.

## Guidance

Only genuine structured guidance events appear. Management optimism does not create a guidance state.

## Metrics that matter

Company Memory intentionally retains narrative facts for later analysis. The public metrics section is narrower:

- comparable multi-point series are eligible;
- genuinely numerical one-point facts are eligible;
- one-off narrative facts are not rendered as KPIs.

This prevents a sparse company such as Trellus from receiving artificial metric cards for administration or shareholder recovery.

## Management promises

Open commitments appear first. Delivered, missed or superseded claims remain available as secondary historical evidence.

## Disclosure gaps

`What remains unclear` preserves material missing disclosure and links back to the last relevant RNS. The page never invents a negative point when Company Memory contains no gap.

## RNS history

The company research log retains:

- date and RNS type;
- analyst verdict and takeaway;
- Signal;
- market reaction;
- Impact;
- full in-place Analyst Note;
- original source link.

## Visual source of truth

The company page uses the same production tokens as the Pass 3 monitoring sheet:

- `#03080d` page background;
- `#46d7ff` cyan accent;
- Helvetica Neue / Helvetica / Arial typography;
- square edges;
- thin research-sheet rules;
- uppercase monitoring labels;
- oversized editorial ticker hierarchy;
- one-column mobile disclosure.

It is a company research sheet, not an app dashboard and not a collection of cards.

## Navigation

Every company/ticker line in the AIM RNS feed links to `/company/{ticker}`. Company RNS history can open the full note in place or return to the corresponding dated monitoring feed.

## Access and deployment

Company pages retain the server-validated private-beta cookie. A locked deep link returns the beta entrance and then redirects the user back to the requested company page after successful authentication.

The production topology remains:

```text
Postgres + smallcaps-ai + AIM Ingestion
```

The previous Streamlit Company Intelligence remains available under `/legacy` during migration.
