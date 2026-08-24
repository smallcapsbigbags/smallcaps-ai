# Pass 5 — Unified Product QA

## North star

Smallcaps.ai must behave as one continuous investor workflow rather than two adjacent pages:

1. scan the AIM RNS monitoring sheet;
2. open the full Analyst Note;
3. move into Company Intelligence;
4. inspect the current investment case and historical RNS record;
5. return to the exact dated announcement in the Feed without losing context.

The release is not complete when the Feed and Company pages work independently. The round trip must be deterministic, shareable, keyboard-accessible and safe behind the private-beta gate.

## Audit findings

Pass 5 found six integration defects that were not visible in the isolated Pass 3 and Pass 4 audits.

### 1. Company-to-Feed deep links were not consumed

Company Intelligence generated URLs in the form:

```text
/?date=YYYY-MM-DD&open=SOURCE_ID
```

The Feed always loaded the latest market day and ignored both query parameters. A user could therefore click **OPEN IN RNS FEED** and land on the wrong day with no announcement expanded.

### 2. Private-beta access dropped query state

The access gate preserved `request.url.path` but not `request.url.query`. An expired beta session therefore removed the dated RNS destination before authentication.

### 3. Feed company navigation depended on a MutationObserver wrapper

Ticker links and the inline **COMPANY RESEARCH** action were added after rendering by a second script. The visible journey worked, but ownership of navigation was split across two asynchronous renderers.

### 4. Historical company announcements had no dated Feed action

Only the current company position linked back to the monitoring sheet. Historical RNS rows offered the original source and the Analyst Note but no exact Feed return.

### 5. Mobile hid the sign-out control

The responsive stylesheet removed `.text-action` below 900px. A private-beta user on mobile had no visible way to end the session.

### 6. Research tables lacked explicit assistive semantics

Company guidance, metrics, promises and history were visually tabular but used generic grid elements without table, row, column-header and cell roles.

## Implemented contract

### Shareable Feed state

The Feed now reads and validates:

```text
date=YYYY-MM-DD
open=SOURCE_ID
```

An exact dated request loads that market day, selects the page containing the requested announcement, expands the row, loads the Analyst Note, scrolls the row into view and places keyboard focus on its disclosure control.

Opening or closing an announcement updates the URL using `history.replaceState`, making the current RNS view shareable without adding noisy browser-history entries.

### Deterministic round trip

Every Company Intelligence history row now exposes:

```text
OPEN IN FEED →
```

The URL is built from the public `source_id` and the displayed London market date. The current view retains **OPEN IN RNS FEED**, so both current and historical research resolve to the same Feed contract.

### Single owner for Feed navigation

`research.js` now renders ticker/company links and the expanded **COMPANY RESEARCH** action directly. The former `feed-company.js` MutationObserver enhancement is removed.

### Beta destination preservation

The private-beta entrance now retains both path and query string. It also rejects protocol-relative destinations and control-character injection attempts before issuing a redirect.

### Mobile session completion

The responsive header keeps **Sign out** visible and uses compact status labels at phone widths. The sign-out and company-to-Feed actions retain mobile touch targets.

### Accessibility and presentation polish

Company research grids receive explicit table semantics after render. Generic `Point in time` labels are presented as `LATEST REPORTED` on the public metrics sheet. The visible Feed footer no longer advertises the legacy implementation; `/legacy` remains available as an operational rollback surface.

## Pass 5 browser acceptance

The dedicated `scbb-pass5-unified-product-audit` workflow runs the product with private-beta mode enabled and deterministic preview data. It verifies:

- rejected and accepted beta authentication;
- exact query-string return after authentication;
- direct dated Feed loading;
- automatic row expansion and focus;
- Feed search, reset, materiality and grouping controls;
- Feed-to-company navigation;
- current company-to-Feed return;
- historical company-to-Feed return;
- public table semantics;
- mobile sign out and touch targets;
- desktop and mobile horizontal overflow;
- duplicate DOM IDs;
- sparse/unknown company failure handling;
- browser console and page errors;
- runtime tracebacks and API errors.

The workflow uploads six visual checkpoints covering the entrance, current RNS round trip, historical RNS round trip and mobile journey.

## Architecture unchanged

Pass 5 does not change:

- AIM ingestion;
- Analyst 3.3;
- Company Memory construction;
- the `scbb-monitoring-v1` or `scbb-company-v1` schemas;
- PostgreSQL;
- the three-service Railway topology;
- the AIM Ingestion schedule.
