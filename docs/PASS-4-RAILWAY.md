# Pass 4 — Private Railway Deployment and Live Validation

## Objective

Deploy the audited V1 privately, validate the complete live data path and collect enough operational evidence to decide whether the branch is ready for visual refinement and eventual merge.

## Railway service layout

Create one Railway project with four services:

```text
PostgreSQL
Web
Daily AIM ingestion cron
Market reaction cron
```

All application services use the same GitHub repository and branch:

```text
smallcapsbigbags/smallcaps-ai
build/aim-intelligence-v1
```

### Web service

Config path:

```text
/railway.json
```

The service validates runtime and database schema before deployment, starts Streamlit on Railway's `$PORT`, exposes `/_stcore/health`, restarts on failure and remains private behind the beta access code.

### Daily AIM ingestion cron

Config path: `/railway.ingest.json`

Schedule: `*/10 6-18 * * 1-5`

Railway cron is UTC. The broad weekday window intentionally covers both GMT and BST. PostgreSQL deduplication means repeated runs do not reanalyse known RNSs.

### Market reaction cron

Config path: `/railway.prices.json`

Schedule: `*/15 7-17 * * 1-5`

The worker uses the official `XLON` session calendar, requests one Yahoo quote per ticker and freezes the event-session close after the exchange closes.

## Required variables

```text
DATABASE_URL=<Railway PostgreSQL reference>
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-5.4-mini
OPENAI_DEEP_MODEL=gpt-5.4
OPENAI_MAX_OUTPUT_TOKENS=12000
PROMPT_VERSION=analyst-engine-2.0
DEEP_SEARCH_BATCH_SIZE=5
MAX_DOCUMENT_CHARS=45000
MIN_EVIDENCE_CHARS=40
INVESTEGATE_AIM_MAX_PAGES=8
MAX_AI_ITEMS=36
PRIVATE_BETA_MODE=true
APP_BETA_PASSWORD=<secret>
APP_ADMIN_PASSWORD=<different secret>
MARKET_DATA_ENABLED=true
MARKET_DATA_TIMEOUT_SECONDS=25
DEFAULT_WATCHLIST=SPR,IHC
```

Never commit secrets.

## Runtime validation

Each service runs `python -m jobs.validate_runtime --service <web|ingestion|prices> --create-schema` before deployment. Validation blocks ephemeral SQLite, missing private-beta credentials, unavailable PostgreSQL and missing service-specific dependencies.

## Live acceptance sequence

1. Deploy PostgreSQL and Web; verify beta and Admin access gates.
2. Submit one controlled RNS through Admin QA and verify publishable/review/blocked behaviour.
3. Run `python -m jobs.ingest_daily` twice and confirm source-ID deduplication.
4. Run `python -m jobs.run_analyst_benchmarks` and review all 16 cases.
5. Run `python -m jobs.update_prices` during and after an LSE session; verify `event_day_return` and frozen close.
6. Test desktop/mobile Feed, Note, search, sorting, watchlist, empty and error states.

## Rollback

Do not merge the feature branch during private validation. Stop cron services, retain PostgreSQL for diagnosis, redeploy the prior feature-branch commit and use `job_runs` plus Railway logs to diagnose failures.

## Pass 4 completion gate

Pass 4 completes only when all services deploy, live PostgreSQL/OpenAI/Investegate/Yahoo checks pass, the benchmark is reviewed, no private-quality data leaks publicly, one event close freezes, browser/mobile QA passes and the owner approves the private-beta output.
