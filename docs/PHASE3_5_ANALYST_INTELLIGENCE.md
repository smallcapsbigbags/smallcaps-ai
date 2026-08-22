# Phase 3.5 — Analyst Intelligence Layer

## Purpose

Company Memory gives Smallcaps.ai continuity. The Analyst Intelligence Layer adds a second discipline:

> Which numbers matter for this type of business, and are those numbers moving together in a way that supports management's story?

This is not a valuation model or a sector database. It is an evidence-bound analytical checklist designed to prevent generic RNS summaries from treating revenue growth as the right answer for every company.

## Product behaviour

For each material RNS, Smallcaps.ai now:

1. infers a cautious company archetype from the current announcement and eligible point-in-time history;
2. supplies the analyst with the sector's economically meaningful KPI checklist;
3. runs the normal Analyst Engine and Company Memory comparison;
4. tests the structured draft for important contradictions or missing relationships;
5. supplies those findings to the existing final consistency review;
6. sends unresolved material findings to the review queue rather than silently publishing them.

No additional OpenAI call is introduced. The existing initial analysis and final consistency review remain the only Analyst Engine calls.

## Supported analytical profiles

The deterministic profile library currently covers:

- housebuilders;
- property companies and REITs;
- recruitment companies;
- software and SaaS companies;
- specialist lenders;
- mining and mineral-resource companies;
- oil and gas producers;
- life sciences and medical technology;
- retailers and consumer companies;
- industrial contractors and project-service companies;
- professional services, legal and consulting companies;
- a conservative general small-cap profile when classification evidence is weak.

The profile contains priority KPIs, relationship checks and sector questions. It is explicitly labelled as a heuristic checklist, not a company-reported fact.

## KPI examples

The profile changes the analyst's attention, not the source evidence.

- **Recruitment:** net fee income, conversion, headcount and permanent/contract mix rather than gross contractor payroll pass-through.
- **Housebuilding:** completions, reservations, average selling price, margin, land bank and net debt.
- **Property:** EPRA NTA/NAV, occupancy, LTV and disposal price versus book value.
- **Software:** ARR/recurring revenue, retention, gross margin, bookings and cash burn.
- **Lending:** loan book, net interest margin, cost of risk, arrears, capital and liquidity.
- **Mining:** production, grade, recovery, AISC, capex and cash.
- **Life sciences:** clinical/regulatory milestone, cash runway, burn and funding to the next milestone.
- **Retail:** like-for-like sales, gross margin, inventory and net debt.
- **Contracting:** order book, project margin, utilisation, working capital and cash conversion.
- **Professional services:** fee income, fee earners, utilisation, profit, lock-up and acquisition funding.

A KPI is used only when the current RNS or eligible Company Memory actually contains it. The engine must never manufacture a missing metric or denominator.

## Deterministic relationship checks

The first release detects the following investor-relevant tensions:

### Growth quality

- the meaningful top line rises while profit grows materially more slowly;
- revenue rises while gross, operating or EBITDA margin falls;
- acquisition-led growth is disclosed but the organic contribution is not quantified.

### Earnings versus cash

- profit or EBITDA improves while cash conversion weakens;
- profit improves while cash falls or net debt rises;
- guidance remains unchanged while balance-sheet risk worsens.

### Pipeline versus delivery

- order book or backlog rises while current profit or margin deteriorates;
- the analysis risks treating total contract value as current-year revenue or earnings.

### Sector-specific tensions

- recruiter NFI is disclosed but ignored in favour of gross billings;
- life-sciences progress is presented without the disclosed funding need;
- loan-book growth is accompanied by higher arrears, impairments or cost of risk;
- ARR growth is accompanied by weaker retention, higher burn or lower cash;
- production growth is accompanied by higher unit costs;
- retail sales growth is accompanied by margin or inventory pressure.

Each finding carries a code, evidence summary, direction and investor-facing terms that must be explained before publication.

## Resolution standard

A finding is not considered resolved merely because its raw KeyFact labels appear in the note.

The investor-facing analysis must explain the relationship. For example:

> Revenue rose 33%, but EBITDA increased only 9% and margin fell to 11.1% from 13.5%. Growth included acquisitions and the organic contribution was not disclosed.

A table containing `Revenue`, `EBITDA`, `Margin` and `Net debt` without that interpretation does not pass the check.

## Point-in-time and evidence controls

- Profiles use only the current announcement and eligible pre-RNS Company Memory.
- Historical comparators must match period family, unit, currency and reported/calculated basis.
- H1 is not treated as comparable with FY.
- The profile cannot introduce outside sector data or broker forecasts.
- The current RNS cannot enter its own prior context.
- The model must verify each deterministic finding before changing the note.
- Unresolved review-level findings prevent automatic publication.

## Cost design

The profile and contradiction detector are deterministic Python code.

They add:

- no web search;
- no database table;
- no additional model call;
- only a compact KPI checklist and evidence-backed finding payload to the existing prompts.

The public Company Intelligence page remains zero-token.

## Acceptance tests

The zero-token Analyst Intelligence benchmark contains locked cases across professional services, recruitment, life sciences, lending, software, mining, retail, contracting, housebuilding and a clean no-false-positive case.

Run it with:

```bash
python -m jobs.run_intelligence_benchmark \
  --output analyst-intelligence-results.json
```

Acceptance requires every locked case to:

- infer the expected profile;
- detect all required relationship findings;
- avoid all forbidden false positives.

Before production merge, Analyst 3.1 must also pass the existing Company Memory and Phase 2 gold-standard regressions so the new checklist does not degrade factual grounding, Impact judgement or plain-English output.

## Deferred work

This release does not include:

- automatic sector classification from a commercial reference database;
- broker consensus or valuation multiples;
- semantic merging of differently named KPIs without evidence;
- bespoke company financial models;
- Buy/Sell/Hold recommendations;
- user-configurable sector models.

The objective is narrower: make every new RNS analysis more commercially intelligent while preserving the evidence, provenance and restraint established in Phases 2 and 3.
