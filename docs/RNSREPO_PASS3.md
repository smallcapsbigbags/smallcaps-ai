# RNSRepo Pass 3 — real-source acceptance

This pass changes reliability and evaluation, not the card design. `main` remains
the requested delivery branch. Public no-login cards remain temporary and bounded.

## Before comparing models

Nine full issuer announcements plus the previously supplied Transense announcement
are fixed by normalized-source SHA-256 in `benchmarks/rnsrepo/corpus-manifest.json`.
Distributor AI summaries/navigation are excluded. Every issuer paragraph and table
cell is retained in order, including risk notes and subsequent events. Nested layout
tables must not duplicate content. Raw publisher snapshots are short-lived CI
artifacts, not permanent product ingestion. Springfield's normalized publisher copy
is 73,147 characters; this is NOT a claim to reproduce the user's exact 77,609-character
clipboard content. Fusion's corrected full results are 107,489 characters.

Initial free preflight found Springfield and ValiRx exceeded the complete request
limit after citation expansion. The fix checks the entire encoded payload, iteratively
reducing optional selected context locally. Mandatory disclosure selection is not
relaxed. No additional model calls and no length-based flagship fallback.

## Live comparison protocol

`python -m jobs.evaluate_rnsrepo` is free preflight by default. `--live` explicitly
permits at most 20 calls across at most two approved small models, one attempt per
case/model. Default comparison: gpt-5-mini and gpt-5-nano. SDK retries remain zero.
Hash-check every source before the first call; keep every failure in the report.
Candidate copy may be logged only for these fixed public fixtures, never user input.
The real production validators still run. A completed benchmark is not a launch
approval and does not claim human semantic review. Dollar estimates use measured
input/cached/output usage (including failed attempts) and separately mark unpriced
requests; call/byte/token limits are not an invoice-level hard dollar guarantee.

## Predeclared human acceptance rubric

Every card must be reviewed against its complete source, not only selected excerpts.
A clean JSON object or successful quotation match is necessary, not sufficient.
Check displayed amounts, units, periods, signs and their correct metric; actual vs
forecast/proposal; material limitations and financing risk; no invented arithmetic,
company identity, advice or claims of independent authentication. Source references
must remain exact and verifiable. No semantic/critical omission error is acceptable
in the evaluated card. Report separately withheld drafts and wrongly accepted cards.

Case-specific minimum review:
- SPR: revenue £243.7m, adjusted PBT £12.9m (not £11.9m statutory), year-end net BANK
  cash £1.2m at 31 May 2026, proposed dividend 3.0p. Cash story must qualify the later
  £20.7m acquisition payment; do not imply today's cash. Lower land sales explain
  the reported profit decline. Initial worker-housing agreement is not a full order.
- FAB: corrected margin 58.3%, not superseded 53%; disclose the correction and explicit
  going-concern material uncertainty/additional funding need, not an optimistic summary.
- VAL: cash £970,564 at 30 June 2026; no committed additional funding and material
  uncertainty must stay visible. Do not imply a guaranteed twelve-month cash runway.
- AEO: revised revenue floor £22.6m and PBT floor £1m are expectations for year ending
  31 December 2026; PBT excludes non-trading FX, not statutory actual earnings.
- GEO: £1.035m placing BEFORE expenses at 0.06p is separate from the initially targeted
  £250k retail offer; the latter is not already raised. Do not use GGP as the issuer.
- SRC: €110m cash/debt-free business consideration plus €8m non-core assets; completion
  expected Q4 subject to regulatory consents, not a completed acquisition. Target EBITDA
  €18m relates to 2025 and is not the acquirer's group EBITDA or acquired annual revenue.
- NG: 141,904 shares vested at nil cost; 66,930 sold for tax. Not an open-market purchase.
- HEAD: continuing revenue £188.8m fell; financing/disposals under discussion are not
  secured funds. Do not conflate a strategic review with an announced sale of the company.
- HAYD: approximately 28% thermal improvement and discussions representing 200MW are
  not contracted sales/revenue; installation timing is a target subject to qualification.
- TRT: funded six-month DEVELOPMENT, expected production Q2 2027, expected annual
  revenues >£0.7m only following successful development and future deployments.

## Release evidence required

Live complete-source results, documented human review, independent corruption and
holdout formatting tests, measured latency/tokens/cost, CI including PostgreSQL
admission tests, unchanged frontend hashes, final deployed browser journeys without
login. A ten-document comparison is a small sample, not an accuracy guarantee or
proof of the cheapest model in all workloads. Runtime model changes require an
explicit reviewed result, not merely a cheaper list price.
