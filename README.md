# smallcaps.ai — AIM Intelligence

Smallcaps.ai is an AI-powered UK small-cap equity research product. It analyses the daily AIM RNS flow, explains what changed and why it matters, and stores the structured point-in-time record required to make later company analysis better.

## Product North Star

Help an AIM investor answer three questions:

1. **What changed?**
2. **Why does it matter?**
3. **What did the market do?**

The public V1 is deliberately narrow:

```text
Daily AIM Intelligence Feed
        ↓
Analyst Note
        ↓
Original RNS / lightweight company RNS history
```

The full Company Intelligence page is deferred until enough first-party history has accumulated naturally.

## Locked daily pipeline

```text
Investegate AIM catalogue
      ↓
PostgreSQL source-ID deduplication
      ↓
Routine filtering and material prioritisation
      ↓
OpenAI web search for evidence on selected new rows
      ↓
Evidence integrity gate
      ↓
Point-in-time company context
      ↓
Analyst Engine 2.0
      ↓
Deterministic guardrails
      ↓
Publication quality gate
      ↓
Versioned Railway PostgreSQL
      ↓
Public Feed / Analyst Note
      ↓
Separate market-reaction worker
```

OpenAI is not responsible for inventing the day's catalogue. Investegate identifies the exact announcement; OpenAI retrieves and corroborates evidence after discovery.

## Public product

The Streamlit application now routes between:

- **Feed** — current `publishable` records only, ranked by Impact or time;
- **Analyst Note** — Takeaway, Key Numbers, Before → Today → Read-through, Analyst View, Supports / Challenges, Guidance, What to Watch, market reaction and source links;
- **Company RNS history** — a lightweight accumulated timeline, not a synthetic backfilled thesis;
- **Private Analyst QA** — available only through `?view=admin` and protected by `APP_ADMIN_PASSWORD`.

Review-required analyses never enter the public product or future Company Memory.

## Impact

The user-facing Feed exposes one signal:

```text
● IMPACT LOW / MEDIUM / HIGH / CRITICAL
```

The dot colour communicates read-through:

- green — favourable;
- red — adverse;
- amber — mixed or uncertain;
- grey — no meaningful directional read-through.

No Positive/Negative, Buy/Sell, materiality score or five-circle gauge is displayed.

## Market reaction

`python -m jobs.update_prices` attaches the normal daily move versus the previous trading-session close.

Price reaction remains separate from the original AI Impact and never changes it. One market-data request is made per ticker, even where several RNSs share the same trading session.

## Repository layout

```text
analyst/              Analyst Engine 2.0, schemas, evidence and quality gates
database/             PostgreSQL models, immutable analysis storage and product reads
ingestion/            Investegate discovery, OpenAI evidence retrieval and manual fallback
market/               London-session logic, Yahoo MVP client and reaction service
product/              Pure public-product formatting helpers
ui/                   Unified light Feed, Analyst Note, company history and Admin QA
jobs/                 Daily ingestion, market reaction and benchmark entrypoints
prompts/              Analyst Engine 2.0 contract
benchmarks/           Difficult-announcement definitions
docs/                 Architecture and pass records
tests/                Deterministic acceptance suite
app/, intelligence/   Preserved original visual prototypes
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

The default local database is SQLite at `data/smallcaps.db`. Railway production uses `DATABASE_URL` and psycopg 3.

## Jobs

Daily AIM ingestion:

```bash
python -m jobs.ingest_daily
```

Intraday / closing market reaction:

```bash
python -m jobs.update_prices
```

Credentialled Analyst Engine benchmark:

```bash
python -m jobs.run_analyst_benchmarks
```

## Railway variables

```text
DATABASE_URL=<Railway PostgreSQL URL>

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

APP_ADMIN_PASSWORD=<secret>

MARKET_DATA_ENABLED=true
MARKET_DATA_TIMEOUT_SECONDS=25
DEFAULT_WATCHLIST=SPR,IHC
```

No secrets should be committed.

## Tests

```bash
pytest -q
```

GitHub Actions also validates Python compilation and the benchmark JSON contract.

## Branch strategy

- `main` — protected current version;
- `build/aim-intelligence-v1` — AIM Intelligence V1 build;
- `rns-xray` — read-only donor/reference repository.

See:

- `docs/PASS-1-AUDIT-RESULTS.md`
- `docs/PASS-2-ANALYST-ENGINE.md`
- `docs/PASS-3-PRODUCT.md`

## Known pre-launch dependencies

- credentialled live Investegate/OpenAI/PostgreSQL smoke test;
- live 16-case Analyst Engine benchmark;
- formal database migrations for any non-fresh Railway database;
- scheduler concurrency protection and a persisted retry ledger;
- confirmed RNS and market-data commercial rights;
- Railway cron configuration for ingestion and price updates.
