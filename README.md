# smallcaps.ai — AIM Intelligence

Smallcaps.ai is an AI-powered UK small-cap equity research product. It analyses the daily AIM RNS flow, explains what changed and why it matters, and stores the point-in-time record required to improve later company analysis.

## North Star

1. **What changed?**
2. **Why does it matter?**
3. **What did the market do?**

```text
Daily AIM Intelligence Feed
  → Analyst Note
  → Original RNS / lightweight Company RNS History
```

Full Company Intelligence remains deferred until first-party history accumulates naturally.

## Daily pipeline

```text
Investegate AIM catalogue
  → PostgreSQL source-ID deduplication
  → routine filtering / material prioritisation
  → OpenAI web-search evidence retrieval
  → evidence integrity gate
  → point-in-time company context
  → Analyst Engine 2.0
  → deterministic guardrails / quality gate
  → versioned PostgreSQL
  → Feed / Analyst Note
  → separate LSE-calendar market-reaction worker
```

## Product integrity

- public pages expose current `publishable` runs only and never call OpenAI;
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

The public product is Feed, Analyst Note and Company RNS History. Admin QA is available at `?view=admin`.

## Jobs

```bash
python -m jobs.ingest_daily
python -m jobs.update_prices
python -m jobs.run_analyst_benchmarks
python -m jobs.validate_runtime --service web --create-schema
```

## Railway

Use one project with PostgreSQL plus three services deployed from `main`:

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

GitHub Actions validates pushes and pull requests targeting `main`, including Python compilation, benchmark JSON and Railway config JSON.

## Branch strategy

- `main` — live AIM Intelligence V1 source of truth;
- `build/aim-intelligence-v1` — retained only as historical build branch;
- `rns-xray` — read-only donor/reference repository.

See `docs/PASS-1-AUDIT-RESULTS.md`, `docs/PASS-2-ANALYST-ENGINE.md`, `docs/PASS-3-PRODUCT.md`, `docs/PASS-3-AUDIT-RESULTS.md` and `docs/PASS-4-RAILWAY.md`.

## Private-beta limitations

- use a fresh Railway database until formal migrations are introduced;
- missed event-session closes are surfaced as stale but not reconstructed automatically;
- +1/+5/+20 event returns are not populated yet;
- live Investegate/OpenAI/Yahoo/browser validation requires connected Railway credentials;
- RNS and market-data commercial rights remain public-launch dependencies.
