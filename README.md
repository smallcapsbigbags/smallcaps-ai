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

## Analyst 3.1 — Company Memory + Sector Intelligence

Every new RNS is analysed against a deterministic, point-in-time company memory built from earlier publishable Smallcaps.ai records for the same company.

The memory contains:

- the latest captured guidance for each metric and period;
- repeated comparable KPIs and balance-sheet figures;
- open, delivered, missed or superseded management promises;
- recent disclosure gaps;
- recent Impact history;
- the source ID, date and RNS behind every historical item.

The model receives a compact memory snapshot plus a small number of exact earlier RNS records. Company Memory does not use future information, broker forecasts or a synthetic historical thesis. The public Company Intelligence page is generated from PostgreSQL and does not call OpenAI.

Analyst 3.1 also adds a deterministic sector-KPI and contradiction layer. It treats company archetypes as analytical checklists rather than reported facts, and only uses KPIs actually disclosed in the current RNS or eligible history. It tests relationships such as revenue versus profit and margin, earnings versus cash/debt, ARR versus cash burn, loan growth versus credit quality, production versus unit costs, backlog versus current profitability, and acquisition-led growth versus the disclosed organic contribution.

Unresolved material contradictions are routed to the review queue rather than silently published. The intelligence layer adds no new web-search call, no additional Analyst Engine call and no new database table.

Coverage remains **building** until at least six analysed announcements span 12 months. Until then the product shows the history it genuinely has rather than pretending to offer complete long-term coverage.

## Daily pipeline

```text
Investegate AIM catalogue
  → PostgreSQL source-ID deduplication
  → routine filtering / material prioritisation
  → OpenAI web-search evidence retrieval
  → evidence integrity gate
  → deterministic point-in-time Company Memory
  → relevant prior-RNS selection
  → deterministic sector-KPI checklist
  → Analyst Engine 3.1
  → deterministic contradiction checks
  → final evidence-bound consistency review
  → deterministic guardrails / quality gate
  → versioned PostgreSQL
  → Feed / Analyst Note / Company Intelligence
  → LSE-calendar market-reaction cycle
```

For the launch MVP, the market-reaction cycle runs at the start of the reliable AIM ingestion cron. A newly analysed RNS is picked up on the next ten-minute cycle. A separate price-only Railway service remains optional and uses the same advisory lock, so overlapping cycles skip rather than duplicate work.

## Analyst method

Analyst 3.1 preserves the Phase 2 gold-standard method:

```text
EXTRACT → VERIFY → RANK → COMPARE → CHALLENGE
→ INTERPRET → SCORE → WRITE → CONSISTENCY REVIEW
```

It adds the Phase 3 continuity and sector-quality tests:

```text
Management said → Facts now show → Smallcaps.ai explains the change
Meaningful KPI → Related economics → Funding / repeatability check
```

The analyst must:

- lead with today's genuinely new economic information;
- use the strongest valid prior comparator;
- avoid comparing different periods, units, currencies or accounting bases as though they were equivalent;
- distinguish new guidance from repeated guidance and avoid double-counting an earlier upgrade;
- test open management promises only where today's evidence genuinely allows it;
- prioritise the economically meaningful KPI for the business rather than defaulting to revenue;
- test whether growth is translating into profit, margin, cash and balance-sheet improvement;
- keep reported facts, Smallcaps.ai calculations and Smallcaps.ai interpretation visibly separate;
- preserve the source and date behind historical comparisons;
- write in plain English for a normal investor.

## Product integrity

- public pages expose current `publishable` runs only and never call OpenAI;
- Company Intelligence is derived only from publishable point-in-time records;
- no current RNS can enter its own prior context because history is restricted to `published_at < current announcement`;
- production analysis and live chronology validation use the same context builder;
- unsupported comparator source IDs block publication;
- reported and calculated figures remain separate memory series;
- unresolved review-level intelligence findings cannot auto-publish;
- sector profiles are heuristic checklists and cannot become company-reported facts;
- production prompt metadata is locked to the version shipped in `analyst/version.py`;
- review records require audited owner approval before publication;
- facts, guidance and claims preserve the analyst engine's ranked order;
- source-adapter HTTP(S) URLs take precedence over model references;
- Feed date bounds are London/DST correct;
- market sessions use the official `XLON` exchange calendar;
- `event_day_return` is separate from future +1/+5/+20 returns;
- worker runs use PostgreSQL advisory locks and persist status in `job_runs`;
- stale durable worker rows are only reconciled after proving the corresponding advisory lock is idle;
- Railway cannot silently fall back to ephemeral SQLite;
- every Railway deployment runs a zero-token production audit before starting the service.

The production audit verifies PostgreSQL write access, one-current-analysis invariants, public evidence integrity, source links, Feed availability, Company Memory data, worker records and stored market reactions. Unsafe public-data failures block deployment. A historical worker failure remains visible as a warning so it cannot deadlock deployment of the fix; the next scheduled cycle must then prove the new worker.

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
python -m jobs.audit_production --service web --record --reconcile-stale
python -m jobs.run_analyst_benchmarks
python -m jobs.run_gold_standard_benchmark
python -m jobs.run_company_memory_benchmark
python -m jobs.run_intelligence_benchmark
python -m jobs.validate_company_memory --ticker SPR
python -m jobs.validate_company_memory_live --tickers SPR --auto 3
python -m jobs.validate_runtime --service web --create-schema
```

`jobs.ingest_daily` performs the market-reaction cycle before the longer RNS analysis cycle when `MARKET_DATA_ENABLED=true`. `jobs.update_prices` remains available for a separate price-only cron and uses the same lock-safe implementation.

The Company Memory benchmark uses four locked point-in-time cases and no web-search retrieval, so it tests memory behaviour without paying to rediscover the source RNSs.

The Analyst Intelligence benchmarks contain both required-signal cases and false-positive controls. They make no OpenAI call.

The live Company Memory validator reconstructs every covered RNS date directly from PostgreSQL and makes no OpenAI call. It is designed to validate Springfield first, then add companies with deeper and more varied histories.

## Railway

The frozen launch MVP uses one Railway project with PostgreSQL plus two required services deployed from `main`:

```text
railway.json          Web
railway.ingest.json   AIM ingestion + market-reaction cron
```

An optional standalone market-reaction service can use:

```text
railway.prices.json   Price-only cron; safe to overlap because of its advisory lock
```

The following are one-off validation service configs, not continuously running production services:

```text
railway.analyst31-preflight.json        Analyst 3.1 hard-case preflight
railway.benchmark.json                  full gold-standard regression
railway.company-memory-benchmark.json   AI Company Memory regression
railway.company-memory-live.json        zero-token live chronology validation
```

Required variables are documented in `.env.example` and `docs/PASS-4-RAILWAY.md`. No secrets should be committed. Railway production records the code-locked Analyst prompt version even if an old `PROMPT_VERSION` service variable remains configured.

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
pytest -q
python -m jobs.run_intelligence_benchmark \
  --cases benchmarks/analyst_intelligence_cases.json
python -m jobs.run_intelligence_benchmark \
  --cases benchmarks/analyst_intelligence_controls.json
```

GitHub Actions validates pushes and pull requests targeting `main`, including Python compilation, Company Memory continuity, PostgreSQL round trips, the complete discovery-to-Company-Intelligence smoke chain, production-audit behaviour, price-worker idempotency, Analyst Intelligence signal/control benchmarks, benchmark JSON, Company Intelligence rendering and Railway config JSON.

## Branch strategy

- `main` — live AIM Intelligence source of truth;
- `phase3/company-memory` — Phase 3 Company Memory foundation history;
- `phase3/live-company-validation` — Phase 3 chronological live-validation history;
- `phase3/analyst-intelligence-layer` — Analyst 3.1 sector-intelligence release history;
- `launch/pro-pass-2` — production-operation hardening history;
- `build/aim-intelligence-v1` — retained only as historical build branch;
- `rns-xray` — read-only donor/reference repository.

See `docs/MVP_FEATURE_FREEZE.md`, `docs/PHASE-3-COMPANY-MEMORY.md`, `docs/PHASE3_PASS2_LIVE_VALIDATION.md`, `docs/PHASE3_5_ANALYST_INTELLIGENCE.md`, `docs/PHASE3_5_ACCEPTANCE.md`, `docs/PASS-1-AUDIT-RESULTS.md`, `docs/PASS-2-ANALYST-ENGINE.md`, `docs/PASS-3-PRODUCT.md`, `docs/PASS-3-AUDIT-RESULTS.md` and `docs/PASS-4-RAILWAY.md`.

## MVP feature freeze

The launch MVP is limited to:

- daily AIM announcement discovery and analysis;
- the Intelligence Feed;
- full Analyst Notes with original-source links;
- point-in-time Company Memory and Company Intelligence;
- deterministic sector-KPI and contradiction checks;
- review queue and owner approval;
- market reaction where the worker has a valid observation;
- private-beta access control and basic operational status.

New analyst features, portfolio accounts, notifications, valuation models, broker consensus and large historical backfills are post-launch work unless they are required to fix a launch-blocking defect.

## Private-beta limitations

- Company Memory is only as complete as the publishable RNS history accumulated since coverage began;
- differently named metrics are not automatically reconciled unless their structured metric names match;
- formal database migrations remain a production-hardening task, although Analyst 3.1 requires no new table;
- missed event-session closes are surfaced as stale but not reconstructed automatically;
- +1/+5/+20 event returns are not populated yet;
- direct interactive Railway log/database inspection requires a connected Railway credential, although deploy-time production audits run inside Railway itself;
- RNS and market-data commercial rights remain public-launch dependencies.
