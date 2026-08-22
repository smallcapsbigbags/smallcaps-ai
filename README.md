# smallcaps.ai — AIM Intelligence

Smallcaps.ai is an AI-powered UK small-cap equity research product. It analyses the daily AIM RNS flow, explains what changed and why it matters, and preserves the point-in-time company record needed to judge what management said before, what changed today and whether delivery is moving in the promised direction.

## North Star

1. **What changed?**
2. **Why does it matter?**
3. **What did management say before?**
4. **Are the numbers and promises moving in the stated direction?**
5. **What did the market do?**

```text
Daily AIM Intelligence Feed
  → Analyst Note
  → Company Intelligence
  → Original RNS
```

## Analyst 3.0 — Company Memory

Every new RNS is analysed against a deterministic, point-in-time company memory built from earlier publishable Smallcaps.ai records for the same company.

The memory contains:

- the latest captured guidance for each metric and period;
- repeated comparable KPIs and balance-sheet figures;
- open, delivered, missed or superseded management promises;
- recent disclosure gaps;
- recent Impact history;
- the source ID, date and RNS behind every historical item.

The model receives a compact memory snapshot plus a small number of exact earlier RNS records. Company Memory does not use future information, broker forecasts or a synthetic historical thesis. The public Company Intelligence page is generated from PostgreSQL and does not call OpenAI.

Coverage remains **building** until at least six analysed announcements span 12 months. Until then the product shows the history it genuinely has rather than pretending to offer complete long-term coverage.

## Analyst 3.1 — Sector Intelligence

Analyst 3.1 adds a deterministic sector-aware KPI and contradiction layer on top of Company Memory.

Before the note is written, Smallcaps.ai infers a cautious company archetype from the current RNS and eligible history. It supplies a checklist of the economically meaningful KPIs for that type of business. After the first draft, deterministic checks test relationships such as:

- revenue or volume growth versus profit and margin;
- earnings versus cash conversion and net debt;
- order book versus current delivery and cash;
- acquisition-led growth versus disclosed organic performance;
- recruiter net fee income versus gross contractor billings;
- life-sciences milestones versus cash runway and funding;
- loan-book growth versus arrears and credit risk;
- ARR growth versus retention and cash burn;
- production growth versus unit costs;
- retail sales versus margin and inventory.

The profile and findings are analytical checklists, not company-reported facts. They cannot introduce an undisclosed KPI, denominator, comparator, sector statistic or valuation input. Valid findings are passed into the existing final consistency review. Unresolved material findings enter the review queue instead of being published automatically.

This layer adds no new model call. It uses deterministic Python plus the existing initial analysis and final consistency review.

## Daily pipeline

```text
Investegate AIM catalogue
  → PostgreSQL source-ID deduplication
  → routine filtering / material prioritisation
  → OpenAI web-search evidence retrieval
  → evidence integrity gate
  → deterministic point-in-time Company Memory
  → relevant prior-RNS selection
  → deterministic sector KPI profile
  → Analyst Engine 3.1 draft
  → deterministic relationship / contradiction checks
  → final evidence-bound consistency review
  → deterministic guardrails / quality gate
  → versioned PostgreSQL
  → Feed / Analyst Note / Company Intelligence
  → separate LSE-calendar market-reaction worker
```

## Analyst method

Analyst 3.1 preserves the Phase 2 gold-standard method:

```text
EXTRACT → VERIFY → RANK → COMPARE → CHALLENGE
→ INTERPRET → SCORE → WRITE → CONSISTENCY REVIEW
```

It adds two Phase 3 disciplines:

```text
Management said → Facts now show → Smallcaps.ai explains the change
Meaningful KPI → Related economics → Contradiction / confirmation
```

The analyst must:

- lead with today's genuinely new economic information;
- use the strongest valid prior comparator;
- choose the economically meaningful KPI for the business when it is disclosed;
- compare growth with profit, margin, cash and debt rather than stopping at the largest headline number;
- avoid comparing different periods, units, currencies or accounting bases as though they were equivalent;
- distinguish new guidance from repeated guidance and avoid double-counting an earlier upgrade;
- test open management promises only where today's evidence genuinely allows it;
- keep reported facts, Smallcaps.ai calculations and Smallcaps.ai interpretation visibly separate;
- preserve the source and date behind historical comparisons;
- write in plain English for a normal investor.

## Product integrity

- public pages expose current `publishable` runs only and never call OpenAI;
- Company Intelligence is derived only from publishable point-in-time records;
- no current RNS can enter its own prior context because history is restricted to `published_at < current announcement`;
- production analysis and live chronology validation use the same context builder;
- sector profiles are deterministic checklists, not reported facts;
- unresolved review-level intelligence findings stop automatic publication;
- unsupported comparator source IDs block publication;
- reported and calculated figures remain separate memory series;
- review records require audited owner approval before publication;
- facts, guidance and claims preserve the analyst engine's ranked order;
- source-adapter HTTP(S) URLs take precedence over model references;
- Feed date bounds are London/DST correct;
- market sessions use the official `XLON` exchange calendar;
- `event_day_return` is separate from future +1/+5/+20 returns;
- worker runs use PostgreSQL advisory locks and persist status in `job_runs`;
- Railway cannot silently fall back to ephemeral SQLite.

## Private beta

```text
PRIVATE_BETA_MODE=true
APP_BETA_PASSWORD=<secret>
APP_ADMIN_PASSWORD=<different secret>
```

The public product is the Feed, Analyst Note and Company Intelligence. Admin QA is available at `?view=admin`.

## Jobs

```bash
python -m jobs.ingest_daily
python -m jobs.update_prices
python -m jobs.run_analyst_benchmarks
python -m jobs.run_gold_standard_benchmark
python -m jobs.run_company_memory_benchmark
python -m jobs.run_intelligence_benchmark
python -m jobs.validate_company_memory --ticker SPR
python -m jobs.validate_company_memory_live --tickers SPR --auto 3
python -m jobs.validate_runtime --service web --create-schema
```

The Company Memory benchmark uses four locked point-in-time cases and no web-search retrieval, so it tests memory behaviour without paying to rediscover the source RNSs.

The Analyst Intelligence benchmark is also zero-token. It checks profile selection, required contradiction findings and false-positive controls across multiple company types.

The live Company Memory validator reconstructs every covered RNS date directly from PostgreSQL and makes no OpenAI call. It is designed to validate Springfield first, then add companies with deeper and more varied histories.

## Railway

Use one project with PostgreSQL plus three production services deployed from `main`:

```text
railway.json          Web
railway.ingest.json   AIM ingestion cron
railway.prices.json   Market reaction cron
```

The following are one-off validation service configs, not continuously running production services:

```text
railway.company-memory-benchmark.json   AI Company Memory regression
railway.company-memory-live.json        zero-token live chronology validation
```

Required variables are documented in `.env.example` and `docs/PASS-4-RAILWAY.md`. No secrets should be committed.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

Local development may use SQLite. Railway must use PostgreSQL through `DATABASE_URL`.

## Tests

```bash
python -m jobs.run_intelligence_benchmark
pytest -q
```

GitHub Actions validates pushes and pull requests targeting `main`, including Python compilation, Company Memory continuity, PostgreSQL round trips, the zero-token Analyst Intelligence benchmark, benchmark JSON, Company Intelligence rendering and Railway config JSON.

## Branch strategy

- `main` — live AIM Intelligence source of truth;
- `phase3/company-memory` — Phase 3 Company Memory foundation history;
- `phase3/live-company-validation` — Phase 3 chronological live-validation history;
- `phase3/analyst-intelligence-layer` — Analyst 3.1 sector KPI and contradiction work;
- `build/aim-intelligence-v1` — retained only as historical build branch;
- `rns-xray` — read-only donor/reference repository.

See `docs/PHASE-3-COMPANY-MEMORY.md`, `docs/PHASE3_PASS2_LIVE_VALIDATION.md`, `docs/PHASE3_5_ANALYST_INTELLIGENCE.md`, `docs/PASS-1-AUDIT-RESULTS.md`, `docs/PASS-2-ANALYST-ENGINE.md`, `docs/PASS-3-PRODUCT.md`, `docs/PASS-3-AUDIT-RESULTS.md` and `docs/PASS-4-RAILWAY.md`.

## Private-beta limitations

- Company Memory is only as complete as the publishable RNS history accumulated since coverage began;
- sector profiles are heuristic and use only the supplied RNS/history, not a commercial sector reference database;
- differently named metrics are not automatically reconciled unless their structured metric names match;
- formal database migrations remain a production-hardening task, although Phase 3 requires no new table;
- missed event-session closes are surfaced as stale but not reconstructed automatically;
- +1/+5/+20 event returns are not populated yet;
- live Investegate/OpenAI/Yahoo/browser validation requires connected Railway credentials;
- RNS and market-data commercial rights remain public-launch dependencies.
