# Phase 3 — Company Memory and Company Intelligence

## Purpose

Phase 3 turns Smallcaps.ai from a strong announcement analyst into a continuously updating company analyst.

The product question is:

> What did management tell investors before, what are they telling investors now, and are the numbers or promised actions moving in the stated direction?

Company Memory must improve today's analysis without allowing old information, future information or synthetic backfill to distort it.

## Product behaviour

For every material new RNS, Smallcaps.ai receives:

1. the exact evidence dossier for today's announcement;
2. a deterministic point-in-time Company Memory snapshot built only from earlier publishable Smallcaps.ai records for the same ticker;
3. up to seven exact earlier RNS records selected for relevance and provenance.

The Analyst Engine then asks:

- what is genuinely new today?;
- what is the strongest valid previous comparator?;
- is guidance new, repeated, upgraded, downgraded, delivered or withdrawn?;
- does today's RNS test an earlier management promise?;
- are related KPIs moving together or diverging?;
- does today's evidence strengthen, weaken or leave the investment case unchanged?;
- what still needs proving?

## Point-in-time integrity

The memory query is restricted to:

```text
same ticker
published_at < current announcement published_at
current analyst version for that announcement
quality_status = publishable
```

The current RNS cannot enter its own prior context. Later RNSs cannot rewrite an earlier analysis. Historical analyst versions remain in PostgreSQL but only the current publishable version of each earlier announcement enters memory.

## Memory data contract

`CompanyMemorySnapshot` contains:

### Coverage metadata

- ticker and company;
- time at which the snapshot was generated;
- first and latest covered RNS dates;
- announcement count;
- coverage span in days;
- `building` or `established` coverage status.

Coverage is `established` only when at least six analysed announcements span at least 365 days. This is a minimum data threshold, not a claim that coverage is complete.

### Current guidance

The latest captured guidance item for each metric and period, including:

- metric;
- period;
- current value or wording;
- status;
- previous value/comparator where available;
- source RNS and date.

Delivered and missed guidance are historical outcomes rather than current forward guidance. Withdrawn guidance remains visible because withdrawal is the current position.

### Comparable KPI series

The memory builder groups only conservatively comparable facts:

- same normalised metric;
- same period family: FY, H1, H2, quarter or point-in-time;
- same unit;
- same currency;
- same basis: reported or Smallcaps.ai-calculated.

It does not merge H1 with FY, reported with calculated, GBP with USD or different units. Numeric change is calculated only where both comparable records contain numeric values.

The public UI presents movement as `up`, `down`, `unchanged` or `unclear`. It does not claim that a movement is good or bad without the Analyst Note's interpretation.

### Management promises

Open and resolved promises contain:

- stable `claim_key`;
- claim text;
- metric/target value;
- target date;
- status: open, delivered, missed, superseded or not-assessable;
- outcome and source evidence.

A repeated management statement does not count as delivery. The Analyst Engine should reuse the same claim key only when today's RNS genuinely tests the same promise.

### Disclosure gaps

Only gaps raised in the latest few publishable analyses are carried forward. This avoids treating every historic omission as permanently unresolved.

### Recent Impact history

The latest announcement Impact records are supplied as context. Historic Impact does not choose today's colour or score.

## Provenance rules

Every historic item retains:

- `source_id`;
- publication timestamp;
- RNS title;
- original source URL where available.

A deterministic guardrail blocks publication where a generated fact cites a `comparator_source_id` or guidance `previous_source_id` that is absent from eligible prior context.

Calculated facts must remain labelled `calculated` and show their inputs. Reported and calculated facts never share a memory series merely because their labels match.

## Company Intelligence page

The public Company Intelligence page is generated entirely from PostgreSQL. It does not call OpenAI.

It contains:

- coverage status and coverage period;
- analysed RNS count;
- current guidance;
- repeated KPIs and balance-sheet measures;
- open management promises;
- delivered/missed/superseded promises;
- recent disclosure gaps;
- the full publishable RNS timeline.

Each memory item links back to its source RNS where available. Existing Analyst 2.2 records remain usable; new records are produced by Analyst 3.0.

## Cost design

Company Memory itself has no incremental model call. It is deterministic database compression.

The new RNS still uses the existing Analyst Engine call and final consistency review. The additional cost comes only from sending a compact memory snapshot and selected prior records in the prompt. The Company Intelligence page has no token cost.

## Failure behaviour

Smallcaps.ai should fail safely when:

- the source evidence is missing;
- a calculated figure lacks visible inputs;
- a comparator source cannot be traced to eligible history;
- the model claims established coverage without the deterministic threshold;
- a historic comparison mixes incompatible periods, currencies, units or bases;
- an explicit adverse disclosure disappears from the note.

Blocked outputs are not public and are not allowed to contaminate future Company Memory.

## Acceptance criteria

Phase 3's first release is acceptable when:

- deterministic memory tests pass for guidance, KPIs, claims and gaps;
- H1/FY and reported/calculated data remain separate;
- the current RNS cannot leak into prior context;
- unsupported comparator source IDs block publication;
- SQLite and PostgreSQL integration tests pass;
- the Company Intelligence UI escapes untrusted text and labels calculations clearly;
- a live memory-aware RNS regression set demonstrates that today's main change remains primary while valid history improves the comparison;
- production Railway web and ingestion services deploy with `PROMPT_VERSION=analyst-engine-3.0-company-memory`.

## Deferred Phase 3 work

The first release intentionally does not include:

- synthetic 12-month AI backfill;
- broker consensus history;
- full valuation models;
- automatic semantic reconciliation of differently named KPIs;
- user-authored research notes;
- long-horizon +1/+5/+20 market-reaction returns;
- account-level watchlist alerts.

Those are separate productisation choices. The current priority is trustworthy company continuity from the daily RNS record.
