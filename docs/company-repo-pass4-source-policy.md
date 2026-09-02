# Company Repository Pass 4 — announcement source policy

Smallcaps.ai separates three concerns:

1. **Discovery** — identify the exact AIM announcement.
2. **Evidence** — retrieve the strongest accessible issuer, FCA NSM or official RNS source.
3. **Memory** — persist the analysed event, source URLs and company KPI history.

## Discovery modes

### `disabled`

Fail-closed mode. Existing News, Watchlist and Company repositories remain available, but no new announcement catalogue is read.

### `licensed`

The public-launch mode. `AIM_LICENSED_FEED_URL` must point to an authorised JSON feed. The adapter accepts a list or an object containing `records`, `announcements`, `items` or `data`.

Each row must contain:

- `ticker` (or `tidm` / `symbol`)
- `published_at` (ISO 8601)
- `headline` (or `title`)
- `source_url`
- optional `company` and `categories`

`AIM_LICENSED_FEED_TOKEN` is sent as a Bearer token when present.

### `owner-test`

Private-beta continuity mode only. This retains the legacy Investegate catalogue with LSE.co.uk cross-check/fallback. It is blocked unless:

- `PRIVATE_BETA_MODE=true`
- `ALLOW_UNLICENSED_OWNER_TEST_CATALOGUES=true`

The runtime refuses this mode once private beta is disabled. It must not be treated as a public or commercial launch source.

## FCA NSM

The FCA National Storage Mechanism is used as an authoritative verification and historical-reconciliation source when an exact matching record is found. It is not treated as a real-time discovery API.

For every incoming announcement, source URLs are deterministically classified and ordered:

1. FCA NSM
2. official RNS / London Stock Exchange
3. other non-mirror source
4. known discovery mirrors

A mirror-only record is labelled as such and is never described as FCA or official verification.

## Historical migration

`python -m jobs.reconcile_source_provenance --apply`

This idempotent job scans existing announcement records, removes duplicate/invalid URLs, promotes retained FCA or official URLs to `source_url`, and reports source coverage. It does not alter announcement text, analyst output, facts, guidance or KPI observations.

## Launch gate

Public launch requires:

- `AIM_DISCOVERY_MODE=licensed`
- a secure `AIM_LICENSED_FEED_URL`
- private beta may then be disabled

Until a licensed feed is configured, Smallcaps.ai may remain in explicit owner-test private beta or switch discovery off.
