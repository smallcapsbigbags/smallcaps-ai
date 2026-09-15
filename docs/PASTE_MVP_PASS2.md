# Paste-first MVP — Pass 2: the output card

## Scope

The empty landing screen keeps its locked copy, layout and input interaction.
The result is now a dedicated, deterministic card renderer with the existing brand
colours, a restrained directional left edge, larger headline, pale metric tiles,
and consistent line graphics. There is no Positive badge, status dot, oversized
impact pill, warning triangle or "The catch" label.

The public hierarchy is identity/date/type, headline, summary, selected numbers,
What changed, What matters, optional More facts, then quiet materiality/provenance.
On desktop, up to four metrics share a row. Four metrics use two columns on small
screens; three metrics use compact stacked rows on phones. Text is never ellipsised
or line-clamped. The card grows to fit its source qualifications.

## Changed boundaries

- `product/paste_card.py` selects indexes into existing facts. It performs no model
  call, string-to-number comparison, valuation or materiality reassessment.
- Results prefer group revenue, profit, net cash/debt and dividend where disclosed.
  Contracts prefer value, duration, timing and revenue. Funding events prioritise
  cash and runway. Other events retain diverse metrics in analyst order.
- This selection is a display heuristic, not proof that a metric is correct or that
  every sector's economically most important KPI has been chosen. Review it in
  Pass 3 against live-model output and a broader holdout set.
- The source-scoped response is versioned `paste-mvp-2` with `paste-card-2` layout.
  `facts` remains complete and unchanged. `metric_indexes`, `rns_type`, and
  `analyst_view` are additive fields; the original request still accepts only text.
- `analysis-card.js` renders text with DOM `textContent`, accepts only allow-listed
  direction tokens and uses static SVG paths. It has no network/storage access.
  `analyse.js` retains submission, polling, recovery and input-state handling.
- The new stylesheet owns the card; removed Pass 1 card rules do not accumulate
  underneath a second result-style override stack.

## Evidence and meaning

Selected facts retain their complete values, labels, periods, as-of dates,
comparators and notes. Calculation inputs stay visible with a Calculated label.
Reiterated/previously disclosed facts retain their information-status label.
No percentage changes, arrows, dates, tickers or missing numeric values are invented.
Fewer than three suitable figures is acceptable: do not manufacture placeholders.

What matters includes the existing analyst view plus the supplied qualifications
and warnings. It is not mechanically a bear case. Exact duplicate paragraphs may
be removed, but different qualifying statements remain visible. Source-warning
facts are surfaced in What matters even when not selected as metric tiles.
Every unselected fact is still accessible under More facts. Unknown identity/date
stays unknown. Pasted text is never presented as independently verified RNS evidence.

The impact control is a native keyboard/touch-accessible disclosure. It exposes
the existing rationale without an additional AI request. Labels remain the public
Routine / Minor / Material / High / Critical mapping; the legacy scoring-rubric
calibration is not changed in this presentation pass.

## Tests

`tests/test_paste_card.py` checks selection, preservation, unknown metadata,
calculated inputs, sparse events, source warnings and isolated renderer loading.
The Springfield/Transense fixture notes are manually authored from excerpts;
funding and sparse cases are synthetic. None is a live-model quality benchmark.

`jobs/check_paste_card.py` runs against the actual locally served app, intercepts
analysis endpoints with schema-validated fixture projections and captures desktop,
tablet, phone and 320px-wide card screenshots. It checks visible qualifications,
all-fact access, source warnings, keyboard/touch impact disclosure, empty metrics,
invalid dates, safe literal markup, long text, duplicate IDs and horizontal overflow.
The `paste-card-pass2` workflow runs with paid analysis disabled and no API key.
The existing Pass 1 flow tests remain in place for polling, failure and retry states.

## Deployment and remaining work

This pass does not merge or deploy the branch, change Railway, stop ingestion,
increase budgets or make paid model calls. The Pass 1 single-process private-beta
and temporary in-memory-job limitations remain. No export, follow-up chat,
public billing or durable history is added.

Pass 3 still needs stronger evidence/assertion contracts, semantic qualifier
validation, materiality calibration and live-model quality/latency/cost checks.
Do not describe good fixture screenshots as proof of live analysis quality.
