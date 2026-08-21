# smallcaps.ai — AIM Intelligence

Smallcaps.ai is an AI-powered UK small-cap equity research product. Its first public product will be a daily AIM Intelligence Feed linked to structured Analyst Notes.

This branch contains **Pass 1: Foundation**. It deliberately does not redesign the public interface. The existing static prototypes remain in the repository while the permanent application architecture is built alongside them.

## North Star

Help an AIM investor understand:

1. **What changed?**
2. **Why does it matter?**
3. **What did the market do?**

Every analysed announcement must also create structured data that makes later company analysis better.

## Pass 1 pipeline

```text
AnnouncementInput
      ↓
Relevant prior company context
      ↓
OpenAI structured AnalystNote
      ↓
Deterministic RNS guardrails
      ↓
Versioned Railway PostgreSQL record
```

The database stores companies, announcements, immutable analyst runs, atomic facts, guidance events, management claims, price reactions and corrections.

## Repository layout

```text
analyst/              Strict schemas, context, OpenAI analysis and guardrails
database/             SQLAlchemy persistence and PostgreSQL DDL
ingestion/            Source boundary and manual foundation ingestion
market/               London market-session and Yahoo reaction logic
prompts/              Foundation Analyst Note contract
streamlit_app.py      Private Pass 1 operator console
pipeline.py           End-to-end orchestration
docs/                 Audit and architecture decisions
tests/                Foundation acceptance suite with a real RNS fixture
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

## Railway variables

```text
DATABASE_URL=<Railway PostgreSQL URL>
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-5.4-mini
PROMPT_VERSION=foundation-analyst-1.0
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

A live OpenAI call is environment-gated because API credentials are never committed.

## Branch strategy

- `main`: protected current version.
- `build/aim-intelligence-v1`: new AIM Intelligence build.
- `rns-xray`: read-only donor/reference repository.

See `docs/PASS-1-AUDIT.md` and `docs/ARCHITECTURE.md` for the exact port/refactor decisions.
