# Launch Repair — Pass 1

This pass repairs the production read paths exposed by the post-merge screenshots.

## Company News

- Customer HTML now embeds a deterministic content fingerprint in every stylesheet and JavaScript URL.
- The fingerprint is generated from the deployed asset bytes, so a browser cannot reuse an older `research.js` against a newer Company News DOM.
- Static assets are explicitly revalidated as a second line of defence.
- The default Company News journey is audited until a real news row replaces the loading skeleton and the monitoring API request is observed.

## The AIM Daily

- An undated newsroom request now falls back to the latest day with at least one publication-safe FULL analysis.
- Explicit dated links remain exact and never silently move to another day.
- Empty weekends, holidays and ingestion-outage days therefore no longer present themselves as fabricated quiet editions on the home page.

## Navigation

The customer journey uses the same order on Company News, Watchlist, Company Intelligence and The AIM Daily:

1. News
2. Watchlist
3. The AIM Daily

## Acceptance

The dedicated `launch-repair-pass1` workflow reproduces the production symptoms against a clean production-shaped database and requires:

- versioned Company News and Daily bootstrap scripts;
- a rendered Company News row, not a permanent skeleton;
- a live monitoring API request;
- latest populated Daily fallback;
- a non-empty Daily article;
- consistent navigation;
- no browser-console, page or server errors.
