# Launch repair Pass 5 — one Smallcaps.ai product

## Objective

Make Company News, Watchlist, The AIM Daily, Company Intelligence and the private-beta entrance feel like one coherent application without changing the underlying analyst, data or publication contracts.

The product should preserve the distinct job of each surface while making navigation, state and visual behaviour predictable everywhere.

## North star

**One product, four investor views.**

- **The AIM Daily** edits the market into a concise briefing.
- **Company News** provides the complete material announcement feed.
- **Watchlist** narrows that feed to companies the investor follows.
- **Company Intelligence** explains the current position and supporting evidence for one company.

A user should be able to move between these views without losing the announcement, market day, edition or personal-watchlist context that led them there.

## Product decisions

### 1. One shared application shell

Every public surface now uses the same:

- Smallcaps.ai wordmark
- primary navigation order
- active-navigation treatment
- AIM live status
- watchlist count
- sign-out action
- mobile two-row header
- footer navigation and research disclaimer

The shared shell is implemented in `product-shell.css` and `product-shell.js`. Page-specific files retain ownership of their content, not global navigation.

### 2. Context survives a company-research detour

Links into Company Intelligence carry only enumerated, first-party context:

- source surface: `news`, `watchlist` or `daily`
- announcement source identifier where available
- Company News market date where available
- AIM Daily edition state and date where available

Company Intelligence uses that context to provide one explicit return action:

- Back to Company News
- Back to Watchlist
- Back to The AIM Daily

No arbitrary return URL is accepted. Dates and edition states are validated before they are reused.

### 3. Watchlist is a product surface, not a hidden filter

The Watchlist keeps the existing combined rolling feed and browser-local persistence, but now has its own clear page identity:

- **Personal Company News**
- **Your watchlist.**
- **Every update from the AIM companies you follow, in one place.**

Its navigation state remains active while the user is reading Company Intelligence reached from the Watchlist. Announcement links return to the same open Watchlist item.

### 4. The AIM Daily stays editorial

The AIM Daily retains its masthead, editions and newsroom hierarchy. It now uses the same application chrome as the other product surfaces and no longer loads the retired dark shared stylesheet.

A company link from an edition carries the edition date and state so the reader can return to the exact briefing.

### 5. One mobile header

At small widths every public surface uses the same two-row structure:

1. wordmark and sign out
2. News, Watchlist and The AIM Daily

Navigation and actions retain a minimum 44-pixel target. The live-status label is removed from the constrained mobile header rather than competing with the core actions.

### 6. One trust statement

Every public surface ends with:

> Independent AIM research. Facts first. Not personal investment advice.

This is deliberately a product-level statement rather than page-specific marketing copy.

## Technical boundaries

Pass 5 is a frontend integration pass. It introduces no new:

- AI call or prompt
- database table or query
- ingestion source
- market-data request
- API schema
- publication-safety rule

The shell enhancer performs no network request and renders no untrusted HTML. It uses safe DOM APIs, a fixed set of recognised surfaces and validated query parameters.

## Acceptance contract

The automated audit covers:

- private-beta destination preservation and light visual foundation
- shared navigation, status, watchlist count and footer
- News → Company Intelligence → News round-trip
- Watchlist → Company Intelligence → Watchlist round-trip
- AIM Daily → Company Intelligence → AIM Daily round-trip
- active navigation state on all four investor views
- desktop and mobile header geometry
- 44-pixel mobile actions
- no horizontal overflow or duplicate DOM identifiers
- no browser console or runtime failures
- deterministic screenshots for all principal surfaces

## Out of scope

Pass 5 does not redesign the editorial content inside The AIM Daily, alter Company News card density, change the Company Intelligence decision hierarchy or move the Watchlist out of browser-local storage. Those existing product decisions remain intact.
