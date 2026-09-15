# Pass 3 — paste evidence and bounded validation

## Scope
The Pass 2B HTML, CSS, graphics, editorial style and renderer remain unchanged.
No deployment, Railway variables, budgets, schedules, database migration, history,
public access or follow-up chat is included.

## Implemented path
Paste -> existing analyst with EvidenceAnalystNote -> deterministic draft checks ->
existing review when needed -> original guardrails/quality checks -> final evidence
check -> original card projection. Ingestion keeps AnalystNote and its existing policy.
Paste permits at most two requests, no third repair pass, and no SDK automatic retries.
Other engine consumers retain their original retry settings.

## Evidence
Reported facts and narrative fields carry short source quotations. Fact assertion type
is separate from basis: actual, expected, proposed, conditional, calculated,
not-disclosed or source-warning. Dependency quotations bind conditions to their facts.
Quotes must occur in the pasted text; only whitespace differences are accepted. Records
include document hash, original character spans and deterministic anchor identifiers.
This is metadata, not extra reader-facing prose. The unverified-source disclaimer stays.

Checks target unsupported figures/comparators, invented/missing quotes, outside sources,
forecast/proposal/condition changes, bounds, cash/debt dates, fiscal periods, subsequent
payments alongside a cash story, and unsupported guidance upgrades. Unresolved findings
prevent a completed card; the original text remains available for retry/review.

## Arithmetic
Decimal arithmetic normalises common currencies, k/m/bn, pence, percentages and basis
points. Only two-operand percentage-change, ratio-as-percent, difference and sum are
supported, with source-backed operands and visible inputs. Cross-currency calculations,
zero denominators, non-positive percentage baselines and arithmetic on bounds fail.
Explicit £000/£m table headers are supported. No general expression evaluator is used.
This is not a complete accounting parser or proof of economic comparability.

## Materiality
Uses the existing public 1–5 rubric: Routine, Minor, Material, High, Critical. Direction
remains separate. The legacy internal impact_level mapping stays compatible; score 3
still renders Material. Notes record basis, certainty, horizon and supporting evidence.
Financial scale needs supported, distinct amount/denominator facts with matching units
and annual periods. Unknown scale can still support a Material operational event.
Survival risk is not reduced for lacking a revenue denominator. High ratings based
on customer prestige or routine/unknown context trigger review.
These are rubric and regression controls, NOT empirical calibration against human analysts.

## Verification
Hand-annotated SPR/TRT excerpt controls, synthetic numerical/administrative/funding
controls and deliberately corrupted notes test the checks. Stubbed responses exercise
the real engine/review/adapter and final gate, including the two-request limit. Existing
browser suites continue to test the unchanged renderer. No live response is implied.

## Explicit live smoke test
Preflight makes no model/network request:

```sh
python -m jobs.check_paste_live --output /tmp/paste-live-preflight.json
```

In a separately configured local/staging process with a capped test key already in
OPENAI_API_KEY and an explicitly chosen OPENAI_MODEL:

```sh
python -m jobs.check_paste_live --live --model "$OPENAI_MODEL" \
  --case trt --max-output-tokens 8000 --output /tmp/paste-live-trt.json
```

Maximum two cases, two requests per case, 12,000 input characters per case, and
2,000–12,000 output tokens per request. No retries; stop after the first failure.
These limits are NOT a provider-side monetary cap. CI runs preflight with the key empty.
Reports record hashes, model/versions, usage/latency on completed calls, and prose for
human review. Failures record exception class only, not raw provider errors or secrets.
Passing a smoke check still requires human review of meaning, omissions and writing.
The smoke-test inputs are excerpts, not comprehensive full-RNS evaluations.

## Live readiness and known limits
The local workspace has no API key. Railway exposes configured key names but not secret
values; its agent cannot execute the working branch separately without deployment.
Credential configuration or an empty error search does not establish available budget.
No production change or credential extraction was attempted. Live acceptance is pending.

A matching quote does not prove relevance or source authenticity. Heuristic checks can
have false positives/negatives. Semantic association, missing material facts, negation,
ambiguous tables and accounting comparability are not exhaustively verified. Invalid
structured output/refusals fail closed, not into an unlimited repair loop. Extra evidence
metadata may increase tokens per analysis; quality, latency and cost need live measurement.
The single-process private beta and temporary in-memory jobs/results remain unchanged.
