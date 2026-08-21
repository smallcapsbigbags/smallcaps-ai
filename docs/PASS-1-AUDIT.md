# Pass 1 Repository Audit

## Decision

- `smallcapsbigbags/smallcaps-ai` is the production destination.
- `main` remains untouched.
- `build/aim-intelligence-v1` is the protected build branch.
- `smallcapsbigbags/rns-xray` remains a read-only donor/reference repository.

## Destination: `smallcaps-ai`

The existing repository is a static visual prototype. Its HTML, research examples and image mock-ups remain intact. Pass 1 adds a Python application and persistence foundation alongside those assets; it does not redesign or delete them.

| Existing area | Decision | Reason |
|---|---|---|
| `app/index.html` | Preserve | Useful visual and interaction reference |
| `intelligence/index.html` | Preserve | Useful concept/reference; not the production backend |
| `education/` | Preserve | Outside Pass 1 scope |
| `research/` | Preserve | Existing content remains recoverable |
| Mock-up images | Preserve | Design archive |
| Root README | Replace on feature branch | Needs accurate build/deployment guidance |

## Donor: `rns-xray`

| Donor component | Decision | Destination / treatment |
|---|---|---|
| `rnsxray/models.py` | Port + refactor | `analyst/models.py`; retain strict Pydantic validation and Impact 1–5 |
| `rnsxray/analysis_guardrails.py` | Port | `analyst/guardrails.py`; retain deterministic adverse-disclosure and guidance checks |
| `rnsxray/context_selector.py` | Port | `analyst/context_selector.py`; no vector database required |
| `rnsxray/analyzer.py` | Refactor | `analyst/analyzer.py`; preserve one structured call and source-id integrity |
| `research_model/*` | Reference now; refine in Pass 2 | Initial consolidated prompt lives in `prompts/FOUNDATION_ANALYST.md` |
| `rnsxray/investegate_daily_source.py` | Port + adapt | `ingestion/investegate_daily.py`; this is the locked V1 Daily AIM ingestion source |
| `daily_aim_service_v2.py` | Refactor | `ingestion/daily_service.py`; same discovery/evidence sequence, but Postgres replaces daily JSON caching |
| `daily_live_pricing.py` | Port | `market/pricing.py`; retain London session handling and previous-close methodology |
| File cache / daily JSON | Retire as system of record | Railway Postgres becomes permanent memory |
| Existing Streamlit UI | Reference only | Final feed/note UI belongs to later passes |
| Pure OpenAI catalogue discovery (`daily_aim_source.py`) | Do not use as primary V1 path | Deterministic Investegate discovery is more controlled; OpenAI search remains the detailed evidence layer |

## Locked ingestion flow

```text
Investegate AIM catalogue
      ↓
Ticker / company / timestamp / headline / URL
      ↓
Postgres source_id deduplication
      ↓
OpenAI web-search evidence retrieval for new announcements
      ↓
Issuer IR / official LSE-RNS corroboration preferred
      ↓
Analyst Engine
      ↓
Guardrails
      ↓
Versioned Postgres persistence
```

Manual ingestion remains only for owner testing, QA and recovery.

## Pass 1 deliverable

The feature branch now contains the permanent pipeline:

```text
Daily AIM source or manual fallback
      ↓
AnnouncementInput
      ↓
Relevant prior company context
      ↓
Structured AnalystNote
      ↓
Deterministic guardrails
      ↓
Versioned Postgres records
      ├── companies
      ├── announcements
      ├── analyst_runs
      ├── facts
      ├── guidance_events
      ├── management_claims
      ├── price_reactions
      └── corrections
```

## Explicitly deferred

- Final Daily Feed visual implementation
- Final Analyst Note visual implementation
- Company Intelligence UI
- Historical AIM backfill
- Licensed deterministic RNS feed replacement for commercial production
- Full price-worker scheduling
- Authentication and public user accounts
- Prompt benchmarking and difficult-announcement evaluation suite beyond the foundation fixtures
