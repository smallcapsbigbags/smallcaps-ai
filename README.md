# smallcaps.ai — AIM Intelligence

Smallcaps.ai is an AI-powered UK small-cap equity research product. Its first public product is a daily AIM Intelligence Feed linked to structured Analyst Notes.

This branch contains:

- **Pass 1:** permanent ingestion, evidence, database and pricing foundations;
- **Pass 1 audit:** publication-integrity and provenance corrections;
- **Pass 2:** Analyst Engine 2.0, quality gate and difficult-announcement benchmark suite.

The existing static prototypes remain in the repository. `main` is unchanged.

## North Star

Help an AIM investor understand:

1. **What changed?**
2. **Why does it matter?**
3. **What did the market do?**

Every analysed announcement must also create structured data that improves later company analysis.

## Locked Daily AIM ingestion path

```text
Investegate AIM catalogue
      ↓
deterministic discovery of today's RNS rows
      ↓
PostgreSQL source_id deduplication
      ↓
routine administrative rows stored without deep AI
      ↓
investment-relevant rows prioritised
      ↓
OpenAI web search for detailed evidence on selected new rows
      ↓
issuer IR / official LSE-RNS corroboration preferred
      ↓
evidence-integrity gate
      ↓
relevant prior company context
      ↓
Analyst Engine 2.0
      ↓
deterministic RNS guardrails
      ↓
publication quality gate
      ↓
versioned Railway PostgreSQL record
```

OpenAI does not invent the daily catalogue. Investegate identifies the exact announcement; OpenAI retrieves and corroborates detailed evidence afterwards.

Unavailable or blocked evidence is **not persisted as completed research**. It remains eligible for a later retry.

Manual ingestion is retained only for QA, testing and recovery.

## Analyst Engine 2.0

The default analytical method is:

```text
EXTRACT → VERIFY → RANK → COMPARE → CHALLENGE
        → INTERPRET → SCORE → WRITE
```

The strict output includes:

- Impact colour, score, level, rationale and drivers;
- headline and takeaway;
- facts with basis, periods, comparators and provenance;
- new versus reiterated information;
- Before → Today → Read-through;
- Analyst View;
- Supports / Challenges;
- guidance events;
- management claims;
- watch items;
- disclosure assessment;
- source references, warnings and confidence.

The public Feed will display colour and `LOW / MEDIUM / HIGH / CRITICAL`, not positive/negative labels or investment recommendations.

## Quality states

- `publishable` — no deterministic publication issue;
- `review` — stored for owner review before public display;
- `blocked` — not persisted; evidence or analysis must be retried/corrected.

Guardrail failures such as an omitted going-concern warning, covenant breach, profit warning or unsupported calculated ratio block persistence.

## Repository layout

```text
analyst/              schemas, classification, context, analysis, guardrails,
                      evidence checks, quality gate and benchmark evaluator
benchmarks/           canonical difficult-announcement cases
database/             SQLAlchemy models, PostgreSQL DDL and repository
ingestion/            Investegate/OpenAI Daily AIM source and manual fallback
jobs/                 Railway ingestion and live benchmark entrypoints
market/               London session and Yahoo reaction foundation
prompts/              Analyst Engine 2.0 contract
docs/                 architecture, audit and pass specifications
tests/                deterministic foundation and Analyst Engine tests
app/, intelligence/   preserved visual prototypes
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run streamlit_app.py
```

The default local database is SQLite at `data/smallcaps.db`. Production uses Railway PostgreSQL.

## Daily ingestion

With `OPENAI_API_KEY` configured:

```bash
python -m jobs.ingest_daily
```

## Live analyst benchmark

```bash
python -m jobs.run_analyst_benchmarks
```

The benchmark uses API credits and writes `benchmark-results.json`.

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
APP_ADMIN_PASSWORD=<private console password>
```

No secrets should be committed.

## Tests

```bash
pytest -q
```

CI compiles the application and runs the deterministic suite without making live OpenAI or Investegate calls.

## Branch strategy

- `main`: protected current version;
- `build/aim-intelligence-v1`: AIM Intelligence build;
- `rns-xray`: read-only donor/reference repository.

See:

- `docs/ARCHITECTURE.md`
- `docs/PASS-1-AUDIT.md`
- `docs/PASS-1-AUDIT-RESULTS.md`
- `docs/PASS-2-ANALYST-ENGINE.md`
