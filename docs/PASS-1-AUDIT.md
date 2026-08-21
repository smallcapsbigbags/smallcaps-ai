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
| `daily_live_pricing.py` | Port | `market/pricing.py`; retain London session handling and previous-close methodology |
| `daily_aim_service_v2.py` | Refactor concept | Its catalogue/retry workflow will later target Postgres rather than JSON files |
| File cache / daily JSON | Retire as system of record | Railway Postgres becomes permanent memory |
| Existing Streamlit UI | Reference only | Final feed/note UI belongs to later passes |
| Web-search RNS discovery | Keep behind source interface only | Useful for testing; not assumed complete or suitable as final licensed feed |

## Pass 1 deliverable

The feature branch now contains the minimum permanent pipeline:

```text
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
- Automated licensed RNS ingestion
- Full price-worker scheduling
- Authentication and public user accounts
- Prompt benchmarking and difficult-announcement evaluation suite beyond the foundation fixtures
