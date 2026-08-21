# Smallcaps.ai AIM Intelligence — Architecture

## North Star

Every decision should help an AIM investor understand **what changed, why it matters and what the market did**, faster and more reliably.

Every analysed announcement must also create structured data that improves later analysis.

## Runtime

```text
Hostinger
  └── smallcaps.ai marketing site

Railway
  ├── Streamlit web service
  ├── PostgreSQL
  ├── Daily AIM ingestion worker
  └── future price worker

OpenAI API
  ├── web-search evidence retrieval for exact discovered RNS rows
  └── structured Analyst Engine 2.0
```

## Daily AIM ingestion

```text
Investegate catalogue
  → exact AIM row metadata
  → Postgres source_id dedupe
  → deterministic routine classification / material prioritisation
  → OpenAI web-search evidence retrieval for selected new rows
  → evidence integrity gate
  → company context selector
  → Analyst Engine 2.0
  → deterministic RNS guardrails
  → publication quality gate
  → versioned PostgreSQL
```

Investegate is the discovery catalogue, not the analytical source of truth. OpenAI searches after an exact announcement has been identified.

Manual ingestion is a QA/recovery fallback.

## Code boundaries

- `ingestion/`: catalogue discovery, evidence retrieval and source normalisation.
- `analyst/evidence.py`: prevents headline-only/fallback analysis.
- `analyst/analyzer.py`: one structured inference call.
- `analyst/guardrails.py`: deterministic adverse-disclosure and guidance checks.
- `analyst/quality.py`: publishable/review/blocked gate.
- `analyst/context_selector.py`: relevant point-in-time history without a vector DB.
- `analyst/evaluation.py`: benchmark evaluation.
- `database/`: versioned persistence; no research reasoning.
- `market/`: market data only; price never changes original Impact.
- `pipeline.py`: orchestration.
- `jobs/`: Railway worker entrypoints.
- `streamlit_app.py`: private QA console, not the final Feed.

## Persistence rules

1. `announcements.source_id` is immutable and unique.
2. Deduplication happens before web-search evidence retrieval.
3. Unavailable/blocked analysis is not persisted as completed research.
4. Re-analysis creates a new analyst run.
5. Exactly one run per announcement is current.
6. Previous runs remain available.
7. Facts, guidance and claims link to the exact run that created them.
8. Corrections are separate records.
9. Market reactions are stored after Impact is frozen.
10. Source evidence, provenance and quality flags are distinct fields.
11. Only current `publishable` analyst runs are eligible for later company context.

## Quality states

- `publishable`: eligible for the eventual public Feed.
- `review`: stored for owner review, not public display.
- `blocked`: not persisted; retry or correction required.

## Company context

The deterministic selector retains the two most recent records and uses remaining slots for economically relevant events. Context is strictly earlier than the current announcement.

No vector database is required for V1.

## Database

Railway provides `DATABASE_URL`. SQLAlchemy uses psycopg 3 for PostgreSQL and SQLite for deterministic local/CI tests.

`schema.sql` is the canonical new-database DDL. No production database has yet been declared migrated; formal migrations are required before altering a deployed schema.

## Deferred

- final Feed and Analyst Note UI;
- Company Intelligence UI;
- historical AIM backfill;
- licensed feed replacement;
- price-worker scheduling;
- public user accounts;
- formal database migration tooling;
- credentialled live benchmark sign-off.
