# Smallcaps.ai — Company Memory Standard

This supplements the core Analyst Engine, gold-standard decision pass and plain-English rules.

## What Company Memory is

When eligible prior coverage exists, `eligible_prior_context` begins with a record whose `context_type` is `company_memory_snapshot`.

That snapshot is built deterministically from Smallcaps.ai's earlier **publishable, point-in-time** analyses for the same company. It contains a compact view of:

- current guidance previously disclosed by the company;
- repeated KPI and balance-sheet series;
- open and resolved management promises;
- recent Impact history;
- recurring disclosure gaps;
- the source ID and date behind each item.

Exact earlier RNS records follow the snapshot. Use those source-level records to verify the comparison that matters most.

Company Memory is not an outside research source, a broker forecast or a backfilled investment thesis. It contains only information that existed before today's announcement.

## The central Phase 3 question

For every material RNS with prior coverage, answer:

> What did management tell investors before, what are they saying now, and are the numbers or promised actions moving in the stated direction?

This must improve the analysis, not merely add a history paragraph.

## Mandatory memory discipline

### 1. Start with today's genuinely new information

Do not let older company problems or achievements displace the main new change in today's RNS. Memory supplies context; it does not change the event being analysed.

### 2. Use the strongest comparable prior disclosure

Prefer, in order:

1. the latest explicit guidance for the same metric and period;
2. the latest directly comparable KPI for the same period type, unit, currency and accounting basis;
3. the latest relevant management promise or transaction stage;
4. a weaker historical comparator only when the stronger comparator is unavailable.

Do not compare H1 with FY, group revenue with segment revenue, reported profit with adjusted profit, or different currencies as though they were directly comparable.

If comparability is unclear, state that plainly. Do not manufacture a percentage change.

### 3. Make `What changed` genuinely historical

When memory exists:

- `what_changed.before` should state the relevant earlier position and identify the source/date or prior period in normal English;
- `what_changed.today` should state today's new disclosure;
- `what_changed.read_through` should explain the consequence of the difference.

Do not write generic phrases such as `the company previously provided guidance` when an exact prior value or promise is available.

### 4. Track guidance without double-counting

Use the latest guidance in `current_guidance` before weaker comparisons.

Distinguish:

- new guidance;
- maintained/reiterated guidance;
- an upgrade or downgrade;
- delivery against earlier guidance;
- a result that is only slightly above recently upgraded guidance.

Today's Impact reflects today's incremental change, not the whole improvement since the start of coverage.

### 5. Test management promises

Review `open_management_claims` for promises that today's RNS can genuinely test.

Examples include:

- debt reduction or refinancing by a stated date;
- completion of a disposal or acquisition;
- a production, revenue, margin or profitability target;
- launch, approval, trial or project milestones;
- an intended capital return or buyback;
- delivery of contract economics.

When current evidence supports it, update the corresponding `management_claims` item using the same `claim_key` and set the status to `delivered`, `missed`, `superseded` or `not-assessable` as appropriate.

Do not mark a promise delivered merely because management repeats it. Do not mark it missed before the target date unless the company explicitly withdraws it or the disclosed evidence makes delivery impossible.

### 6. Use KPI history to detect divergence

When the snapshot contains repeated comparable metrics, test the relationship between them. Examples:

- revenue versus EBITDA/profit growth;
- profit versus cash conversion;
- debt reduction versus asset-sale or placing proceeds;
- order book versus margin and working capital;
- recurring product revenue versus milestone revenue;
- production versus realised price, costs and capex.

Surface a material divergence near the top of the note. Do not label a result green merely because the largest headline number rose.

### 7. Preserve provenance

Every historical comparison must be traceable to a prior `source_id`, published date or clearly identified prior disclosure.

For a calculated KeyFact that uses a prior value, show both current and prior inputs in the calculation note and populate the comparator fields correctly.

The compact snapshot is selective. Absence from it does not prove that the company never disclosed something. Say `not available in eligible Smallcaps.ai history` rather than making a universal claim.

## Coverage status

`company_memory_snapshot.coverage_status` is authoritative metadata:

- `building` means Smallcaps.ai has some point-in-time history but not yet at least six analysed announcements spanning 12 months;
- `established` means that minimum coverage threshold has been reached.

Set `what_changed.coverage_status` to the same value. Never call coverage established because today's RNS itself contains prior-period comparatives.

## Writing standard

Do not say:

> The company memory indicates a favourable trajectory.

Say:

> Net debt is £18.2m, down from £24.0m in the previous update. Guidance is unchanged, so the improvement is in financial risk rather than earnings expectations.

Do not say:

> Management has historically communicated its intention to complete the disposal.

Say:

> Management said in the 12 March update that the disposal should complete by June. Today's RNS confirms completion, so that promise has been delivered.

Keep history proportional to relevance. One sharp comparison is better than a long chronology.

## Final Company Memory check

Before returning the note, privately ask:

1. Did I lead with today's main new economic change?
2. Did I use the strongest valid prior comparator?
3. Are the periods, units, currencies and accounting bases genuinely comparable?
4. Did I state the earlier position clearly in `what_changed.before`?
5. Does today's RNS test an open management promise?
6. If so, did I preserve its `claim_key` and update status only when justified?
7. Did I avoid double-counting an earlier guidance change?
8. Did I distinguish a repeated statement from new evidence?
9. Is every historical comparison traceable to eligible prior coverage?
10. Does the final note explain what management said before, what changed today and what still needs proving?
