# SmallcapsBigBags Migration — Pass 2: Monitoring Read Model & API

**Baseline:** `0397d4f2f23d53ed09f128449455eabc7ecd91bc`  
**Branch:** `product/scbb-monitoring-pass2`

## Objective

Expose the Analyst 3.3 monitoring-sheet contract as one stable, versioned, read-only product interface before the SmallcapsBigBags frontend is ported.

Pass 2 does not redesign the website and does not create a second database. The existing Streamlit product and the monitoring API run in one ASGI process against the same PostgreSQL records and the same `publishable` publication gate.

## Source of truth

The API is an adapter over the existing structured Smallcaps.ai record:

- announcement and company metadata;
- current publishable Analyst Run;
- structured facts;
- guidance events;
- management claims;
- market reaction;
- Company Memory carried from earlier publishable RNS facts;
- original source links and provenance.

It never asks another model to rewrite the research.

## Versioned row contract

Schema version: `scbb-monitoring-v1`

Each monitoring row exposes the exact fields needed by the existing SmallcapsBigBags sheet:

| Monitoring column | API field | Source |
|---|---|---|
| Company | `ticker`, `company`, `market`, `isin` | `companies` |
| RNS | `published_at`, `rns_title`, `rns_type` | `announcements` |
| Signal | `signal` | deterministic `impact_colour` mapping |
| What Changed | `what_changed` | `what_changed.today` |
| AI View | `ai_view` | `analyst_view`, maximum 50 words |
| Outlook | `outlook` | genuine structured guidance states only |
| Market Reaction | `market_reaction` | latest stored event-day price record |
| Balance Sheet | `balance_sheet` | current RNS fact, then latest eligible prior fact |
| Impact | `impact.score`, `impact.level` | stored 1–5 Impact |
| Expanded research | `detail_url` | versioned detail endpoint |
| Original source | `original_source_url` | deduplicated source provenance |

## Balance-sheet continuity

The balance-sheet column uses the following order:

1. the best cash, debt, liquidity, working-capital, covenant or runway fact in today's RNS;
2. otherwise, the latest eligible fact from a previous publishable RNS for the same company;
3. otherwise, `Not disclosed`.

A carried figure is labelled `status="carried"` and retains:

- its fact period or as-of date when stored;
- the source RNS ID;
- the source RNS publication time.

The read model never presents a carried figure as if it were reported today.

## Historical compatibility

Analyst 3.3 already enforces a 50-word AI View. Older publishable records may pre-date that rule.

For the compact monitoring row only, Pass 2 keeps complete leading sentences where possible and otherwise clips the stored view at a word boundary. It does not paraphrase or invent text. The expanded detail retains the full stored Analyst View and records `ai_view_compacted=true` in provenance when this compatibility adapter was used.

## Endpoints

### `GET /api/v1/monitoring`

Returns a paginated monitoring-sheet page.

Supported query parameters:

- `date=YYYY-MM-DD` for one London market day;
- or `date_from` and `date_to` for an inclusive range of up to one year;
- `ticker=SPR` repeated, or `tickers=SPR,IHC`;
- `signal=GREEN` repeated, or `signals=GREEN,AMBER`;
- `outlook=MAINTAINED` repeated, or comma-separated `outlooks`;
- `search`;
- `sort=latest|impact`;
- `limit=1..250`;
- `offset>=0`.

When no date is supplied, the API defaults to the current London day.

### `GET /api/v1/monitoring/{source_id}`

Returns the monitoring row plus expanded research:

- verdict and takeaway;
- full What Changed object;
- all structured evidence facts;
- full stored Analyst View;
- supports/challenges;
- guidance events;
- management claims;
- what to watch;
- disclosure assessment;
- source and model provenance.

### `GET /api/v1/schemas/monitoring-sheet`

Returns the generated JSON schemas for list and detail responses.

### `GET /api/v1/health`

Checks database connectivity and reports the number of current publishable records.

## Public safety

- Only `is_current=true` and `quality_status="publishable"` records are exposed.
- Review-required analysis remains invisible.
- The API is read-only.
- Errors use a stable JSON envelope and do not expose stack traces.
- Responses include `nosniff`, restrictive content-security and explicit cache headers.
- CORS permits read-only browser access so the existing SmallcapsBigBags frontend can consume the API in Pass 3.

## Deployment architecture

Streamlit 1.60 provides an ASGI-compatible `App` with custom routes. `web_app.py` mounts the API alongside `streamlit_app.py`, and Railway starts:

```text
python -m uvicorn web_app:app --host 0.0.0.0 --port $PORT
```

The final production topology therefore remains:

```text
Postgres + smallcaps-ai + AIM Ingestion
```

No fourth Railway service is introduced.

## Acceptance

Pass 2 is complete when:

- the row and detail schemas are strict and versioned;
- current and carried balance-sheet provenance is deterministic;
- legacy AI View compatibility never exceeds 50 words;
- Signal and Outlook use the Pass 1 deterministic rules;
- review records remain hidden;
- list filters and pagination are deterministic;
- API, read-model and deployment-launcher tests pass;
- the production pre-deploy monitoring acceptance passes;
- `/api/v1/health`, list, detail and schema endpoints are reachable in production;
- the existing Streamlit visual journey remains unchanged.
