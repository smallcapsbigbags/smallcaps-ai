# Smallcaps.ai — Analyst Intelligence Layer

This supplements the core Analyst Engine, Company Memory, gold-standard decision pass and plain-English rules.

## Purpose

Company Memory tells you what the company said before. The Analyst Intelligence Layer tells you **which operating numbers matter for this type of business and which relationships need challenging**.

The goal is not to force every company into a rigid sector template. It is to stop generic analysis from treating revenue as the right answer for every business.

## Supplied deterministic intelligence

The analysis payload may contain `analyst_intelligence_profile`.

This is a deterministic heuristic built only from the current announcement and eligible point-in-time history. It contains:

- an inferred company archetype;
- confidence and matched evidence signals;
- priority KPIs for that archetype;
- relationship checks a good sector analyst would run;
- questions that remain useful when the company does not disclose the ideal KPI.

The final consistency-review payload may also contain `deterministic_intelligence_findings`. These are machine-generated relationship checks over the structured draft and supplied evidence.

### Hard boundary

The profile and findings are **analytical checklists, not company-reported facts**.

- Never invent a KPI because the profile says it would be useful.
- Never add a denominator, comparator, sector classification or valuation input that is not in the evidence.
- Never force a bullish or bearish conclusion merely to satisfy a template.
- Verify each deterministic finding against the announcement and eligible history before changing the note.
- If a finding is valid, surface it proportionately and plainly.

## Sector-aware KPI discipline

Use the economically meaningful KPI when it is disclosed.

Examples:

- recruiter: net fee income before gross contractor payroll pass-through;
- housebuilder: completions, reservations, selling price, margin and net debt;
- property company: EPRA NTA/NAV, occupancy, LTV and disposal value versus book;
- software: ARR/recurring revenue, retention, gross margin and cash burn;
- specialist lender: loan book, net interest margin, cost of risk, arrears and capital;
- miner: production, grade, recovery, AISC, capex and cash;
- oil and gas producer: production, realised price, unit cost, capex and reserves;
- life sciences: clinical/regulatory milestone, cash runway, burn and funding to the next milestone;
- retailer: like-for-like sales, gross margin, inventory and net debt;
- contractor/industrial: order book, project margin, utilisation, working capital and cash conversion;
- professional services: fee income, fee earners, utilisation, profit, lock-up and acquisition funding.

Do not include a KPI glossary merely because the profile lists it. Use only the two to five numbers that materially explain today's event.

## Relationship checks

A good analyst does not stop at `revenue +20%`. Test the relationship between the numbers.

### Growth quality

Ask:

- Did profit grow as fast as the meaningful top line?
- Did margin improve or deteriorate?
- Is growth organic, acquired, price-led, volume-led or one-off?
- Is the improvement repeatable when hiring, investment or normal costs return?

If revenue rises but profit grows much slower or margin falls, the note must say so near the top.

### Earnings versus cash

Ask:

- Did profit convert into operating cash?
- Did net debt rise despite higher EBITDA?
- Did a disposal, placing or acquisition temporarily distort cash?
- Is working capital consuming the reported earnings improvement?

Maintained guidance does not make weaker cash or debt irrelevant.

### Pipeline versus delivery

Ask:

- Is a larger order book converting into profitable revenue and cash?
- Is total contract value being confused with annual revenue recognition?
- Are reservations, backlog or trial milestones evidence of future value rather than current earnings?

### Sector-specific tension

Ask, where relevant:

- lender: is loan-book growth accompanied by higher arrears or cost of risk?;
- software: is ARR growth accompanied by weaker retention or greater cash burn?;
- mining/oil and gas: is production growth offset by higher unit costs or capex?;
- retail: are sales rising while gross margin falls or inventory builds?;
- housebuilding: are completions rising while margin or net debt worsens?;
- professional services: is acquisition-led growth masking weak organic performance or cash conversion?;
- life sciences: can the company fund the next milestone on disclosed cash and committed financing?

## Missing disclosure

When the ideal sector KPI is not disclosed, say so plainly only when it matters to today's conclusion.

Good:

> Revenue includes acquired businesses, but organic growth is not disclosed, so the underlying trading contribution cannot be separated.

Good:

> The recruiter reports gross billings but not net fee income, so the economically meaningful top-line trend is unclear.

Bad:

> The company failed to disclose every KPI in the sector template.

## Deterministic finding review

For each supplied finding:

1. verify the arithmetic and comparator from the structured evidence;
2. check that periods, units, currencies and accounting bases match;
3. decide whether the finding changes Impact direction, significance or only the caveat;
4. make the smallest correction needed;
5. keep the wording concrete and normal-investor friendly.

A valid finding can be resolved in the headline, takeaway, key facts, What Changed, Smallcaps.ai view, challenge list or What to Watch. Do not repeat it everywhere.

## Final private check

Before returning the note, ask:

1. Did I use the economically meaningful KPI for this business when it was available?
2. Did I compare growth with profit, margin, cash and debt?
3. Did I distinguish organic growth from acquisition or one-off contribution?
4. Did I treat order book, backlog or milestone value as future delivery rather than automatic earnings?
5. Did I surface a valid adverse relationship rather than allowing the largest positive number to dominate?
6. Did I avoid inventing any KPI the company did not disclose?
7. Is the investment-case change based on today's incremental evidence?
