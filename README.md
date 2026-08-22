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
- recurring disclosure gaps;
- recent Impact history;
- the source ID, date and RNS behind every historical item.

The model receives a compact memory snapshot plus a small number of exact earlier RNS records. Company Memory does not use future information, broker forecasts or a synthetic historical thesis. The public Company Intelligence page is generated from PostgreSQL and does not call OpenAI.

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
  → Analyst Engine 3.0
  → final evidence-bound consistency review
  → deterministic guardrails / quality gate
  → versioned PostgreSQL
  → Feed / Analyst Note / Company Intelligence
  → separate LSE-calendar market-reaction worker
```

## Analyst method

Analyst 3.0 preserves the Phase 2 gold-standard method:

```text
EXTRACT → VERIFY → RANK → COMPARE → CHALLENGE
→ INTERPRET → SCORE → WRITE → CONSISTENCY REVIEW
```

It adds the Phase 3 continuity test:

```text
Management said → Facts now show → Smallcaps.ai explains the change
```

The analyst must:

- lead with today's genuinely new economic information;
- use the strongest valid prior comparator;
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
- review records require audited owner approval before publication;
- facts, guidance and claims preserve the analyst engine's ranked order;
- source-adapter HTTP(S) URLs take precedence over model references;
- reported and calculated figures remain separately labelled;
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
python -m jobs.validate_runtime --service web --create-schema
```

## Railway

Use one project with PostgreSQL plus three production services deployed from `main`:

```text
railway.json          Web
railway.ingest.json   AIM ingestion cron
railway.prices.json   Market reaction cron
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
pytest -q
```

GitHub Actions validates pushes and pull requests targeting `main`, including Python compilation, Company Memory continuity, benchmark JSON and Railway config JSON.

## Branch strategy

- `main` — live AIM Intelligence source of truth;
- `phase3/company-memory` — Phase 3 Company Memory and Company Intelligence work;
- `build/aim-intelligence-v1` — retained only as historical build branch;
- `rns-xray` — read-only donor/reference repository.

See `docs/PASS-1-AUDIT-RESULTS.md`, `docs/PASS-2-ANALYST-ENGINE.md`, `docs/PASS-3-PRODUCT.md`, `docs/PASS-3-AUDIT-RESULTS.md` and `docs/PASS-4-RAILWAY.md`.

## Private-beta limitations

- Company Memory is only as complete as the publishable RNS history accumulated since coverage began;
- formal database migrations remain a production-hardening task, although Phase 3 requires no new table;
- missed event-session closes are surfaced as stale but not reconstructed automatically;
- +1/+5/+20 event returns are not populated yet;
- live Investegate/OpenAI/Yahoo/browser validation requires connected Railway credentials;
- RNS and market-data commercial rights remain public-launch dependencies.
