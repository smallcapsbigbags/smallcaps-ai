# SmallcapsBigBags Migration — Pass 3: Exact Monitoring-Sheet Frontend

**Baseline:** `b9799f119626d42ca6ed89d9f3af9783f18c5470`  
**Branch:** `frontend/scbb-monitoring-pass3`

## Objective

Make the existing SmallcapsBigBags Research monitoring sheet the visible Smallcaps.ai product shell, using the live `scbb-monitoring-v1` read model delivered in Pass 2.

This is not a dark-theme interpretation of the previous Streamlit Feed. The public root is a normal HTML/CSS/JavaScript implementation of the monitoring-sheet pattern:

```text
COMPANY / RNS / SIGNAL
WHAT CHANGED
AI VIEW
OUTLOOK
MARKET REACTION
BALANCE SHEET
IMPACT
```

## Visual source of truth

The SmallcapsBigBags Research page governs:

- near-black background;
- cyan accent;
- off-white primary text and blue-grey secondary text;
- oversized `RNS feed.` hero treatment;
- uppercase analyst-monitoring-sheet labels;
- square, thin-bordered controls;
- dense full-width research table;
- What Changed and AI View as the dominant columns;
- compact signal labels;
- five-dot Impact scale;
- expandable research rows;
- mobile collapse into a one-column monitoring record.

Smallcaps.ai changes the universe and data source, not the visual grammar:

```text
SmallcapsBigBags: Portfolio RNS feed · selected holdings
Smallcaps.ai:      AIM RNS feed · all analysed AIM companies
```

## Public frontend

The public root `/` now serves:

- `frontend/index.html`;
- `frontend/assets/research.css`;
- `frontend/assets/research.js`.

The page requests only the versioned read-only API:

```text
GET /api/v1/monitoring
GET /api/v1/monitoring/{source_id}
```

No analyst logic, financial calculation or publication decision is recreated in the browser.

## Monitoring controls

The exact control language is retained:

- Universe;
- Company;
- RNS Type;
- Signal;
- Impact;
- Sort;
- Impact 3+;
- Group by company;
- Reset.

A search field is included because the Smallcaps.ai universe is AIM-wide rather than six portfolio companies.

The page initially requests the current London market day. If that day has no published records, it searches the preceding fourteen days and displays the latest day that does. This makes weekends, holidays and deterministic preview data behave correctly without inventing a second API rule.

## Expanded research

Each row expands in place. The detail response renders:

- RNS summary;
- key numbers and factual provenance;
- What Changed: before, today and read-through;
- full stored AI View;
- What to Watch;
- outlook and guidance events;
- supports and challenges;
- disclosure gaps and source warnings;
- original RNS link.

Untrusted company and analyst text is inserted through `textContent`, not executable HTML.

## Private beta

`PRIVATE_BETA_MODE` remains enforced at the server-rendered page boundary.

The beta code is validated by Starlette against `APP_BETA_PASSWORD`. Successful access sets a signed, expiring, HttpOnly, SameSite cookie. The password is never embedded in JavaScript and cannot be recovered by inspecting the page source.

## Deployment architecture

The Railway topology remains:

```text
Postgres + smallcaps-ai + AIM Ingestion
```

`web_app.py` now serves:

```text
/                  SmallcapsBigBags-style monitoring sheet
/assets/*           static CSS, JavaScript and icon
/api/v1/*            versioned monitoring API
/legacy/*            previous Streamlit product during migration
```

The current Streamlit implementation is preserved under `/legacy` for QA and rollback while the new root is validated. No fourth service and no second database are introduced.

## Frozen in Pass 3

- AIM ingestion and evidence retrieval;
- Analyst 3.3 prompt and output contract;
- PostgreSQL schema;
- Company Memory;
- publication safety;
- API schema `scbb-monitoring-v1`;
- historical analyses;
- Company Intelligence frontend, which moves in Pass 4.

## Acceptance

Pass 3 is complete when:

- the public root is the monitoring sheet, not the Streamlit Feed;
- all seven canonical columns are visible on desktop;
- filters and client-side sorting operate against API data;
- rows expand into full publication-safe research;
- current and carried balance-sheet context are visually distinct;
- market-reaction pending states remain graceful;
- 1440px, 1280px and 390px journeys pass without document overflow;
- keyboard focus and row toggles remain usable;
- the existing Streamlit app is still reachable under `/legacy`;
- all repository, release, visual and production gates pass.
