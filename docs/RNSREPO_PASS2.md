# RNSRepo Pass 2 — editorial cards and a bounded no-login demo

## Product

RNSRepo / See what matters. / Paste an announcement. Get the important details.
The home screen and card renderer retain the reference design: green brand rail,
large headline and supporting words, illustrated mint tiles, optional What changed,
and an unlabelled amber qualification. Scores, sentiment pills, accounts, saved
repos and search are not added. Missing tickers stay missing. Every existing metric
note, period and qualification remains visible; there is no client-side financial
arithmetic or AI text rewrite. Prompt labels are now encouraged to be 2–4 words.

## Anonymous boundary

RNSREPO_PUBLIC_ENABLED is off by default. Enabling it exposes only the root paste
screen and the bounded card prepare/submit/status flow. PRIVATE_BETA_MODE must stay
true for retained legacy routes. Existing follow-up endpoints retain their beta
checks and compact cards never invoke them.

Anonymous access needs a separate random session secret, the exact public origin,
a valid database and a single web process. Prepare returns a same-origin anti-CSRF
token and an HttpOnly/Secure/SameSite browser cookie; POST requires both and a matching
Origin. The cookie is temporary ownership, not an account. We do not accept client
owner IDs. Another browser cannot fetch a job by guessing its identifier.

Railway X-Real-IP is used for network limits, never the client-controlled forwarded
chain. IPv6 is grouped by /64. Outside Railway use the actual socket peer. A missing
or invalid production edge address fails closed. These controls are not a CAPTCHA:
distributed abuse can exhaust the demo's allowance, but cannot evade the global
persisted allowance just by changing IPs, clearing cookies or restarting the server.

## Spending controls, not a provider-account dollar cap

Default site-wide ceilings: 30 admitted attempts/day (UTC), 10/hour. Additionally,
12/network/day, 6/network/hour and 3/browser/10 minutes. Each admission reserves all
applicable counters in one transaction. Conditional SQL upserts ensure concurrent
requests cannot exceed a bucket. A failed admission rolls back other increments.
Limits survive deploys. Successful duplicate-cache hits consume no additional slot.
Failed jobs keep their reservation. Infrastructure failure never falls back to a
resettable in-memory allowance. A queued scheduling failure may conservatively use
a slot without a model request, which is safer than an uncounted paid request.

The Pass 1 single-request/no-retry/no-flagship path, 30 KB encoded-request bound,
18 KB selected-passage bound and 3,000 output-token bound remain. This is NOT a
monetary guarantee for the whole OpenAI account, nor a general rate limiter for
unrelated legacy/admin endpoints. No automatic paid test runs on normal deployments.

## Storage and privacy

Only one additive table, rnsrepo_demo_limits, is introduced: bucket, attempts,
expires_at. It stores keyed network/browser identifiers and aggregate counters;
no raw IP, RNS text, source hash, card or user account is persisted there. Counters
become eligible for removal within two days and are purged on later admissions.
They may physically remain longer when the app is idle. Source/cards remain in the
existing temporary owner-scoped memory store (~30 minutes after completion); provider
and hosting retention are separate. Existing company data is untouched.

`python -m jobs.prepare_rnsrepo_public` validates public configuration and creates
only this operational table during deployment, without calling OpenAI. To pause
anonymous access set RNSREPO_PUBLIC_ENABLED=false, or stop all analysis with
PASTE_ANALYSIS_ENABLED=false. Never disable the legacy beta flag as a shortcut.

## Verification

- Unit/API tests: owner isolation, cookies, CSRF/origin, invalid input, storage failure,
  restart persistence, cookie rotation/network limits, UTC resets and rollback.
- A real PostgreSQL CI service tests concurrent admission (24 attempts, ceiling 5).
- Browser workflow exercises real local HTTP routes with controlled model outputs;
  desktop/mobile fixtures are explicitly edited examples, not live AI claims.
- Real production browser test is opt-in via the commit marker [rnsrepo-pass2-live].
  It waits for the reviewed build fingerprint, submits only the fixed public TRT
  source once, saves the actual card/screenshots, and never retries a paid request.
- Pass 3 still owns full-document corpus evaluation, especially the exact long SPR
  input. A short-TRT success is not evidence that long annual results are solved.

## Primary references checked for this implementation

- Railway client-IP contract and proxy limitations:
  https://docs.railway.com/networking/public-networking/specs-and-limits
  https://station.railway.com/questions/need-authoritative-railway-client-ip-p-b7a7b4bd
- OWASP same-origin/custom-header CSRF guidance:
  https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- PostgreSQL atomic conditional upsert:
  https://www.postgresql.org/docs/current/sql-insert.html

## Live-test repair: select citations instead of recopying them

The no-login production test reached the provider, but its answer failed source
checks. A fixed-source diagnostic then exposed shortened quotations and a corrupted
currency character, as well as a production condition missing from its metric.
These were correctly rejected; the factual checks were not disabled.

The wire schema now asks the model to choose IDs from a locally constructed catalog
of short verbatim source excerpts rather than generate quotation text. IDs resolve
server-side into the same internal CardDraft and run through the unchanged existing
number, basis, condition and source-offset checks. Unknown IDs and arbitrary quote
objects are rejected. Exact repeated excerpts with the same heading are deduplicated.
Short table units are retained with adjacent original context. The existing request
and output bounds, one-call limit and no-model-escalation policy remain.

This prevents a quotation-copying error from becoming a failed card; it does not
prove semantic entailment or completeness. Wider full-results evaluation is Pass 3.
