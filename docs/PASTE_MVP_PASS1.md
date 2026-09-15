# Paste MVP — Pass 1

## Product contract

**smallcaps.ai**  
**See what matters.**  
**Paste an RNS…**

`/` is the on-demand analyser. `/rns`, `/company/{ticker}`, existing APIs and `/legacy`
remain available. The landing page does not fetch news, prices, watchlists or company
history. Existing private-beta access is retained.

## Implemented flow

1. User pastes one announcement. The complete input is retained; the browser never
   clips pasted text to a maximum length. Inputs over 120,000 characters are rejected.
2. Authenticated GET `/api/v1/analyse` establishes a per-browser signed owner cookie.
3. POST `/api/v1/analyse` accepts `{ "text": "..." }` and returns an analysis ID.
4. An isolated, bounded worker calls the existing `OpenAIAnalystEngine` with no prior
   context. The original review routing, guardrails and publication checks remain.
5. GET `/api/v1/analyse/{id}` returns only that browser's result. Polls do not invoke AI.
6. A deterministic HTML result appears beneath the input. No image-generation API.

The full AnalystNote stays inside the worker. The browser receives the smaller paste
contract, retaining all KeyFact metadata, full summary and relevant qualifications.
The legacy truncation and mixed-unit comparison-arrow functions are not used.

## Source boundary

Pasted text is unverified user content. No source is fetched and no identity lookup is
performed. Company names, tickers and header dates are parsed conservatively; missing
or ambiguous values are omitted. The adapter can pass a null publication timestamp
without relaxing the ingestion AnnouncementInput model. A date-only header is never
promoted into a fabricated publication time. A content hash/URN identifies the source.

Current-text comparatives remain usable. There is no independent company history and
no write to shared company memory, news tables or the public feed. The result must not
claim that the pasted text is authentic, complete or current.

## Operational constraints

This pass is a **single-process, single-replica private beta**, not a public anonymous
paid API. Both the page and analysis access retain the existing beta authentication;
switching PRIVATE_BETA_MODE off does not unlock paid analysis. Keep the existing
APP_BETA_PASSWORD configured. The web service also requires OPENAI_API_KEY.

- PASTE_ANALYSIS_ENABLED: default true; set false for an immediate endpoint kill switch.
- PASTE_MAX_JOBS_PER_HOUR: default 30, hard ceiling 100 per process.
- PASTE_MAX_JOBS_PER_SESSION: default 6 starts per 10 minutes, hard ceiling 20.
- Two concurrent jobs, no unbounded queue, maximum 64 retained jobs.
- Session-scoped duplicate documents reuse the same job/result. Establishing the
  owner cookie before POST also protects a retry after a lost POST response.
- Successful and review-required records expire 30 minutes after completion; cleanup
  runs every minute and on access. Generic failed jobs can be explicitly retried after
  60 seconds, still subject to limits. No automatic resubmission of paid work.
- Jobs and results are in memory, not durable. Restart clears them. Do not horizontally
  scale or run multiple web workers until a shared owner-scoped job store is added.
- Do not put secrets or source text into application logs, URLs or localStorage.
- Provider failures never turn into a fabricated successful card.
- Provider timeouts are 90 seconds per request; the existing engine's bounded retry
  and review behaviour remains. This is not a one-call latency promise.

Application job caps are not a currency budget. Retain provider/project spend limits.
The UI explains that text goes to OpenAI; `store=False` is inherited from the engine.
This does not make a promise about provider retention beyond the configured service.

## Deployment / cutover

This branch does not mutate Railway, stop the existing ingestion service, or change
spending limits. Before MVP cutover:

1. Confirm private-beta settings and a funded, capped API key on the web service.
2. Confirm a single web process/replica. Run a live smoke test with explicit approval.
3. Complete Passes 2–4 (card refinement, analytical hardening, follow-up Q&A).
4. Pause the AIM ingestion cron separately when retiring the always-on product.
   Merely deploying this home page does not stop ingestion spend. Setting
   AIM_DISCOVERY_MODE=disabled skips discovery, but the current job still runs its
   market-reaction maintenance before that check; pausing the cron is clearer.

## Tests

`pytest -q tests/test_paste_mvp.py tests/test_frontend_launch_repair.py`

These are deterministic tests with stubbed model results; they do not prove live model
quality or spend. Run the existing full CI suite as regression coverage. Browser smoke
checks should cover empty/input/loading/success/failure, desktop/mobile, keyboard
submission, malicious text rendered literally, and no automatic POST retry.

## Deliberately deferred

Final tile selection and copy refinement, stronger claim-level evidence/qualifier
validation, unified materiality calibration across legacy views, follow-up chat,
image export/sharing, public billing, durable history and automatic company memory.
