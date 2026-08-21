# Smallcaps.ai AIM Intelligence — Foundation Architecture

## North Star

Every decision should help an AIM investor understand **what changed, why it matters and what the market did**, faster and more reliably.

The foundation must also pass the compounding test: every analysed announcement should create structured data that improves later company analysis.

## Runtime boundaries

```text
Hostinger
  └── smallcaps.ai marketing site

Railway
  ├── Streamlit web service
  ├── PostgreSQL
  ├── future RNS worker
  └── future price worker

OpenAI API
  ├── web-search evidence retrieval for exact discovered RNS rows
  └── structured AnalystNote generation
```

## Daily AIM ingestion — locked V1 path

Smallcaps.ai uses the same Daily AIM source pattern currently working in RNS-Xray:

```text
Investegate AIM catalogue
  → deterministic discovery of ticker / company / time / headline / source URL
  → PostgreSQL source_id deduplication
  → OpenAI web search for dense evidence on NEW announcements only
  → prefer issuer IR and official LSE/RNS evidence for corroboration
  → Analyst Engine
  → deterministic guardrails
  → versioned PostgreSQL persistence
```

Investegate is therefore the discovery catalogue, not the analytical source of truth. OpenAI is not asked to invent the day's catalogue from scratch; it searches only after the exact announcement has already been identified.

Manual ingestion remains available only for testing, QA and recovery.

The source adapter preserves the existing owner-test warning that Investegate may itself expose a filtered catalogue and that commercial display rights must be confirmed before public production use.

## Code boundaries

- `ingestion/investegate_daily.py`: current Daily AIM catalogue discovery + OpenAI evidence retrieval.
- `ingestion/daily_service.py`: Postgres deduplication and daily orchestration into the analysis pipeline.
- `ingestion/manual.py`: fallback manual source for testing/QA/recovery only.
- `analyst/`: strict schemas, context selection, OpenAI inference and deterministic guardrails.
- `database/`: versioned Postgres persistence; no analysis logic.
- `market/`: market-session and quote logic; price never changes the original Impact.
- `pipeline.py`: one-announcement orchestration only.
- `jobs/ingest_daily.py`: Railway-ready daily ingestion entrypoint (`python -m jobs.ingest_daily`).
- `streamlit_app.py`: private Pass 1 operator console, not the final public design.

## Persistence rules

1. `announcements.source_id` is immutable and unique.
2. The Daily AIM service checks source IDs before OpenAI evidence retrieval so already-persisted RNSs do not incur repeat retrieval/analysis cost.
3. Re-analysis creates a new `analyst_runs` row.
4. Exactly one run per announcement is current.
5. Previous runs remain available for audit and evaluation.
6. Facts, guidance and claims link to the exact analyst run that created them.
7. Human corrections are separate records, not silent overwrites.
8. Market reactions are stored after the original Impact is frozen.

## Historical context

Pass 1 ports the deterministic topic-based selector from RNS-Xray. It always retains the two most recent records and uses remaining slots for economically relevant prior events. This avoids an early vector database and keeps model context controlled.

## Production database

Railway provides `DATABASE_URL`. The application normalises common Railway/Postgres URL forms and uses psycopg 3 through SQLAlchemy. SQLite is supported only for local tests and the no-cost foundation demo.

## Pass 1 acceptance gate

A real announcement fixture must complete this path in an automated test:

```text
real RNS text
  → recorded structured analysis
  → guardrails
  → company upsert
  → announcement upsert
  → versioned analyst run
  → atomic facts / guidance / claims
  → retrievable current record
```

A separate source-parser test verifies the current Investegate AIM table format without making a live network call in CI.

Live Investegate/OpenAI calls are environment-gated because API credentials are never committed. The same pipeline and schema are used by both recorded tests and the production OpenAI engine.
