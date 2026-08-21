# Pass 3 — Daily AIM Intelligence Product

## Objective

Turn the audited Analyst Engine and PostgreSQL record into the first usable Smallcaps.ai product without introducing a premature Company Intelligence page.

## Public information architecture

```text
AIM Intelligence Feed
  → Analyst Note
  → Original RNS
  → Company RNS history
```

The public application reads stored research. Opening a page never calls OpenAI.

## Feed

The Feed:

- exposes current `publishable` analyst runs only;
- supports date, search, watchlist and Impact/latest sorting;
- ranks High/Critical records ahead of routine notices;
- gives Low Impact notices less physical space;
- displays colour + `IMPACT LOW/MEDIUM/HIGH/CRITICAL`;
- keeps market reaction visually separate;
- surfaces up to three disclosed key facts;
- links to the Analyst Note, source RNS and company history.

The visual system is one consistent warm off-white research interface with charcoal type, restrained blue actions and green/red/amber/grey reserved for financial meaning.

## Analyst Note

The note displays:

1. ticker, company, RNS type and time;
2. Impact and market reaction;
3. analytical headline;
4. The Takeaway;
5. Key Numbers;
6. Before → Today → Read-through;
7. Analyst View;
8. Supports / Challenges;
9. Guidance;
10. What to Watch;
11. disclosure gaps where relevant;
12. market reaction;
13. original source and company-history links.

It loads the exact stored point-in-time analysis and does not regenerate prose on page view.

## Company RNS history

The company page is deliberately limited to accumulated Smallcaps.ai coverage:

- publishable RNS timeline;
- Impact;
- market reaction;
- note/source links;
- coverage start date and record count.

It explicitly states that full Company Intelligence is building naturally. No historical AI backfill is introduced.

## Market reaction worker

`jobs/update_prices.py`:

- finds publishable announcements whose reaction session is today;
- applies London market-open/close logic;
- requests one Yahoo quote per ticker;
- stores the daily move versus previous close for each relevant announcement;
- freezes the close when run after 16:30 London time;
- never changes the original AI Impact.

After-close and weekend announcements move to the next weekday session. A formal UK exchange-holiday calendar remains a production-hardening item.

## QA separation

The Admin QA route is `?view=admin`.

- it is unavailable unless `APP_ADMIN_PASSWORD` is configured;
- it shows the current owner-review queue;
- manual ingestion remains a QA/recovery mechanism;
- review records remain excluded from public pages and later company context.

## Acceptance gate

Pass 3 is complete when:

1. Feed queries expose only publishable records;
2. Analyst Note and company history are database-backed;
3. no public page invokes OpenAI;
4. watchlist/search/sorting work without user accounts;
5. price updates are grouped by ticker and stored separately from Impact;
6. review records are absent from Feed and company history;
7. the unified light design is used throughout;
8. automated tests and CI pass.

## Operational validation still required

- live Streamlit/Railway rendering;
- live Investegate/OpenAI ingestion;
- live Yahoo market-reaction update;
- live 16-case model benchmark;
- mobile/browser QA;
- final domain and cron configuration.
