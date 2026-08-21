# Pass 3 Audit Results

**Audited branch:** `build/aim-intelligence-v1`  
**Outcome:** Pass 3 accepted after the corrective work below.

## Executive assessment

Pass 3 established the correct public information architecture:

```text
AIM Intelligence Feed
  → Analyst Note
  → Original RNS
  → lightweight Company RNS History
```

The public pages correctly read stored PostgreSQL research and never invoke OpenAI. The audit found several data-integrity, market-session and private-beta operational gaps that needed correction before Railway validation.

## Findings and resolution

| Severity | Finding | Resolution |
|---|---|---|
| High | Key facts, guidance and claims lost the model's materiality order because database reads sorted by creation time and label. | Added persistent `ordinal` fields and ordered all public/context reads by the original model sequence. |
| High | The event-session share-price move was stored in `return_1d`, conflating the announcement-day reaction with the future +1 trading-day return. | Added `event_day_return`; `return_1d`, `return_5d` and `return_20d` are now reserved for later event-study horizons. |
| High | Market-session logic handled weekends but not LSE holidays or early/changed sessions. | Added the `XLON` exchange calendar through `exchange-calendars`; reaction sessions now use official LSE sessions and exact open/close times. |
| High | A missed closing price run could remain invisible. | The price worker now reports stale, unfrozen event sessions in its persisted job result rather than silently treating them as complete. Historical recovery remains an explicit follow-up. |
| High | Model-returned source references could outrank the source adapter's verified URL and unsafe schemes were not filtered at the public boundary. | Source URLs are now restricted to absolute HTTP(S), deduplicated and ordered with adapter-supplied evidence before model references. |
| Medium | London date queries added a fixed 24 hours in UTC, which is wrong on daylight-saving transition dates. | Feed day bounds now use consecutive London midnights before UTC conversion. |
| Medium | Company coverage count and start date were derived from the limited visible timeline. | Added independent count/min queries; truncation is disclosed separately. |
| Medium | The Analyst Note research canvas wrapped only its header while later sections sat outside the canvas. | The complete note now renders inside one keyed research container. |
| Medium | Low-impact records still carried the full four-action toolbar, weakening the intended density hierarchy. | Low-impact rows now retain only Analyst Note and source actions; company/watchlist actions remain on material records and inside notes. |
| Medium | The private deployment exposed the public Feed to anyone with the Railway URL. | Added optional full-app private-beta access controlled by `PRIVATE_BETA_MODE` and `APP_BETA_PASSWORD`. Railway defaults to private-beta mode. |
| Medium | Owner-review records could only be inspected, not approved through an audited workflow. | Added explicit owner approval with a mandatory reason and a permanent `corrections` record. |
| Medium | Cron outcomes existed only in Railway logs and simultaneous workers had no application lock. | Added `job_runs`, PostgreSQL advisory locks, persisted summaries/warnings/errors and an Admin operations panel. |
| Medium | Railway could silently fall back to ephemeral SQLite when `DATABASE_URL` was missing. | Runtime validation now blocks Railway startup unless PostgreSQL is configured. |
| Low | Manual QA ingestion accepted non-HTTP source values. | Manual source URLs now reject unsafe or malformed schemes. |

## Accepted Pass 3 product

- Feed, Note and Company History expose current `publishable` runs only.
- `review` records remain private until explicitly approved.
- `blocked` analysis never enters the public product or Company Memory.
- Public page views incur no OpenAI cost.
- Impact remains independent of market price action.
- Company Intelligence and historical AI backfill remain deferred.

## Remaining limitations after the audit

- Event-session closes missed entirely by the price worker are identified but not automatically reconstructed from historical market data.
- Full +1, +5 and +20 trading-day event returns are schema-reserved but not yet populated.
- The private-beta database must be fresh because formal Alembic migrations are still deferred.
- Yahoo/Investegate remain owner-test MVP dependencies; commercial rights must be confirmed before public launch.
- UI browser/mobile validation and live credentialled ingestion still require a Railway deployment.
