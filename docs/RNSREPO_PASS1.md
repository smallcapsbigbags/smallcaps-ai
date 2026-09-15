# RNSRepo — Pass 1: a card task, not an analyst report

## Scope

The existing `/api/v1/analyse` endpoint now uses `rnsrepo.extractor.extract_card`.
The old analyst engine is retained for legacy routes/tests but is not called by
new paste cards. No database migration, saved repository, search or accounts are
added. The beta login remains until Pass 2 adds bounded anonymous access; merely
turning PRIVATE_BETA_MODE off does not expose a paid anonymous endpoint.

## Request path

Validate the paste -> conservative header parsing -> scan all source locally ->
select bounded verbatim passages -> one structured card request -> focused source
checks -> existing illustrative HTML renderer. Supporting prose remains a first-
class field. There are six top-level model fields, at most four metrics, optional
What changed and qualification. No score, sentiment, investment advice or follow-up
chat on this compact path. Cards and text remain temporary, not a private archive.

The selector preserves source offsets and covers available highlights, outlook,
financial, capital, risk, subsequent-events and commercial sections. Critical
matching blocks are mandatory; overflow fails locally before an AI call. Selection
is heuristic, not exhaustive semantic understanding. A reduced card is labelled
as a summary of selected sections. No model sees a claim of full-source coverage.

## Bounded work and configuration

- At most one Responses API request per attempt; SDK retries disabled.
- No review/repair loop or fallback to a flagship model based on length/errors.
- Selected text/heading limit: 18,000 UTF-8 bytes, 24 passages.
- Complete encoded request limit: 30,000 UTF-8 bytes, including schema/instructions.
- Output limit: 3,000 tokens (including reasoning); SDK timeout: 35 seconds.
- These are byte/output-token bounds, NOT a proven end-to-end SLA or monetary cap.
- `RNSREPO_CARD_MODEL` is independent of legacy OPENAI_MODEL/fallback settings.
- Default `gpt-5-mini` with minimal reasoning; only documented small-model options
  are allowlisted. The cheapest acceptable model is not established until Pass 3.
- `OPENAI_API_KEY` is read only on the server. `store=False`; no tool calls.

Quota, throughput, timeout, refusal, incomplete output, schema and evidence errors
have separate safe codes. All completed paid attempts report model/input/output/
reasoning/cached tokens, elapsed time and result code without source text, provider
bodies or credentials. Incomplete output is checked before parsing JSON.

## Accuracy boundary

Each statement/metric includes a short quotation and passage ID. Checks anchor
quotes in the supplied source and check displayed quantities, bounds, certain
qualifiers, date/bank/adjusted bases and selected post-year-end payments. No new
arithmetic is permitted. No failed draft is presented as a complete card.

These checks DO NOT prove that a quote entails the prose, that a table was correctly
interpreted, that no material paragraph was omitted, or that a pasted RNS is genuine.
The card explicitly remains unverified. Real full-document evaluation is required.

## Verification

`python -m pytest tests/rnsrepo -q` runs source, corruption, budget, response/error,
API wiring and privacy tests. `python -m jobs.check_rnsrepo_frontend` checks the real
renderer using controlled cards at 320/390/768/1280px; it is not a live-model browser
journey. CI runs the full repository suite with real dependencies and archives its
source. The local workspace may not have the production OpenAI SDK installed.

`python -m jobs.check_rnsrepo_card` is a zero-call preflight. `--live` explicitly
allows one model request using the supplied TRT announcement. `--source FILE`
allows operator input without logging the source or its model copy. No probe approves
a launch. The exact 77,609-character failing Springfield paste is not in this fixture;
long-input controls are synthetic and must not be presented as that source.

An opt-in `RNSREPO_DEPLOY_LIVE_CHECK=1` probe is time-bounded at 45 seconds and
blocks deployment if it fails. Its status is reported separately from
Railway health. Turn it off after the explicit test; successful deployment is not
proof that generation passed. No automatic paid probe runs by default.

## Next passes

Pass 2: RNSRepo branding, faithful final card refinements, no-sign-in access with
server-side abuse and spending controls. Pass 3: live full-RNS corpus, semantic
accuracy/omissions, model cost/latency measurements and production acceptance.
Keep legacy database data unchanged. Retire ingestion using both its config file
and service settings so main-branch deploys cannot restart market-wide analysis.
