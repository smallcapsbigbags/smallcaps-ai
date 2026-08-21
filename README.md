# smallcaps.ai — AIM Intelligence

Smallcaps.ai is an AI-powered UK small-cap equity research product. Its first public product will be a daily AIM Intelligence Feed linked to structured Analyst Notes.

This branch contains **Pass 1: Foundation**. It deliberately does not redesign the public interface. The existing static prototypes remain in the repository while the permanent application architecture is built alongside them.

## North Star

Help an AIM investor understand:

1. **What changed?**
2. **Why does it matter?**
3. **What did the market do?**

Every analysed announcement must also create structured data that makes later company analysis better.

## Locked Daily AIM ingestion path

Smallcaps.ai V1 uses the same working pattern as the current RNS-Xray Daily app:

```text
Investegate AIM catalogue
      ↓
Deterministic discovery of today's RNS rows
      ↓
PostgreSQL source_id deduplication
      ↓
Routine administrative rows stored without deep AI
      ↓
Investment-relevant rows prioritised (MAX_AI_ITEMS, default 36)
      ↓
OpenAI web search for detailed evidence on selected new rows only
      ↓
Prefer issuer IR / official LSE-RNS corroboration
      ↓
Relevant prior company context
      ↓
OpenAI structured AnalystNote
      ↓
Deterministic RNS guardrails
      ↓
Versioned Railway PostgreSQL record
```

OpenAI is therefore not responsible for inventing the day's announcement catalogue. Investegate identifies the exact RNS; OpenAI web search retrieves and corroborates the detailed factual evidence before the Analyst Engine runs. True administrative notices do not consume a deep analysis call. Material rows deferred by the daily cap remain unpersisted so they are eligible for the next run rather than being incorrectly marked complete.

Manual ingestion remains available only as a testing, QA and recovery fallback.

The database stores companies, announcements, immutable analyst runs, atomic facts, guidance events, management claims, price reactions and corrections.

## Repository layout

```text
analyst/              Strict schemas, classification, context, OpenAI analysis and guardrails
database/             SQLAlchemy persistence, Postgres DDL and dedupe queries
ingestion/            Investegate Daily AIM source, OpenAI evidence retrieval and manual fallback
jobs/                 Railway-ready daily ingestion entrypoint
market/               London market-session and Yahoo reaction logic
prompts/              Foundation Analyst Note contract
streamlit_app.py      Private Pass 1 operator console
pipeline.py           One-announcement analysis orchestration
docs/                 Audit and architecture decisions
tests/                Foundation acceptance suite with real RNS fixtures
app/, intelligence/   Preserved visual prototypes from the original repo
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

The default local database is SQLite at `data/smallcaps.db`. Production uses Railway's `DATABASE_URL` and psycopg 3.

## Run the Daily AIM ingestion job

With `OPENAI_API_KEY` configured:

```bash
python -m jobs.ingest_daily
```

This checks today's Investegate AIM catalogue, ignores source IDs already stored in PostgreSQL, persists true routine notices without a deep model call, retrieves detailed evidence for selected new investment-relevant rows with OpenAI web search, runs the Analyst Engine and persists the resulting research.

## Railway variables

```text
DATABASE_URL=<Railway PostgreSQL URL>
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-5.4-mini
OPENAI_DEEP_MODEL=gpt-5.4
PROMPT_VERSION=foundation-analyst-1.0
DEEP_SEARCH_BATCH_SIZE=5
MAX_DOCUMENT_CHARS=45000
INVESTEGATE_AIM_MAX_PAGES=8
MAX_AI_ITEMS=36
```

No secrets should be committed.

## Tests

```bash
pytest -q
```

The end-to-end acceptance test uses a real 7 August 2026 Inspiration Healthcare LTIP announcement fixture and a recorded structured analysis. It proves the same production pipeline can:

- ingest the source;
- apply context selection;
- apply deterministic guardrails;
- upsert the company and announcement;
- create versioned analyst runs rather than overwrite history;
- persist atomic facts and management claims; and
- retrieve the current record.

Separate tests verify the Investegate AIM table parser, current routine/ownership/material priority rules, and that Postgres deduplication happens before repeated evidence retrieval.

Live Investegate/OpenAI calls are environment-gated because API credentials are never committed.

## Branch strategy

- `main`: protected current version.
- `build/aim-intelligence-v1`: new AIM Intelligence build.
- `rns-xray`: read-only donor/reference repository.

See `docs/PASS-1-AUDIT.md` and `docs/ARCHITECTURE.md` for the exact port/refactor decisions.
