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
  └── structured AnalystNote generation
```

## Code boundaries

- `ingestion/`: converts an authorised/manual source into `AnnouncementInput`.
- `analyst/`: strict schemas, context selection, OpenAI inference and deterministic guardrails.
- `database/`: versioned Postgres persistence; no analysis logic.
- `market/`: market-session and quote logic; price never changes the original Impact.
- `pipeline.py`: orchestration only.
- `streamlit_app.py`: private Pass 1 operator console, not the final public design.

## Persistence rules

1. `announcements.source_id` is immutable and unique.
2. Re-analysis creates a new `analyst_runs` row.
3. Exactly one run per announcement is current.
4. Previous runs remain available for audit and evaluation.
5. Facts, guidance and claims link to the exact analyst run that created them.
6. Human corrections are separate records, not silent overwrites.
7. Market reactions are stored after the original Impact is frozen.

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

A live OpenAI call is environment-gated because API credentials are never committed. The same pipeline and schema are used by both the recorded test engine and the production OpenAI engine.
