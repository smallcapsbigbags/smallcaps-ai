# Pass 4 — Routed Review Quality Audit

## Objective

Prove that Analyst 3.4 can avoid selected second-pass model calls without weakening the evidence-first analyst standard.

Pass 3 changed routing, not the analytical contract. Pass 4 therefore treats the former always-two-pass full-analysis path as a shadow control rather than assuming the cheaper route is safe.

## Method

The locked benchmark uses representative real AIM announcements already covered by the human-grade gold-standard suite. It deliberately mixes:

- low/moderate contract, trading and technical updates that can exercise the single-pass route; and
- high-risk controls covering profit warnings, takeovers, funding, acquisitions, Rule 9/control and financial results.

For every case the routed Analyst 3.4 note must pass the existing deterministic publication checks and the independent gold-standard evaluator.

When the router chooses `single-pass`, the audit then forces the exact same consistency-review path that the old always-two-pass architecture would have paid for. The routed note and shadow-reviewed note are independently scored against the same evidence and eligible prior context. A separate pairwise evaluator asks only whether the omitted review fixed a material defect.

## Loss-averse acceptance rules

A single-pass case is rejected if the shadow review:

- exposes a material factual, material-fact, comparator, What Changed or unsupported-inference regression;
- changes Impact colour/direction;
- changes Impact materiality by two or more levels;
- improves the human-grade score by more than 3 points; or
- improves factual grounding by more than 1 point.

Every routed note must also remain publishable, pass its case-level gold-standard gate, contain no critical evidence failure and avoid wrong-direction Impact.

The benchmark requires at least two single-pass cases by default. This prevents a false green result in which the router simply sends every case through the expensive second review.

## Cost metric

For `N` full-analysis cases, the old baseline is `2N` analyst calls. Analyst 3.4 uses `N + reviewed_cases` calls. Each accepted single-pass case therefore saves exactly one analyst model call. The audit reports both the count and percentage reduction for the locked case set.

This metric is intentionally separate from the earlier triage saving, where ARCHIVE and LIGHT announcements can avoid the full analyst layer altogether.

## Run

Use the manual `pass4-routing-quality-audit` GitHub Actions workflow, or run:

```bash
python -m jobs.run_routing_quality_benchmark \
  --case-set benchmarks/pass4_routing_case_set.json \
  --output routing-quality-results.json
```

A live run requires `OPENAI_API_KEY`. The result artifact contains the routed note, forced shadow-review note, both independent gold-standard judgements, the pairwise regression judgement, routing reasons and the final call-saving calculation for each case.

Pass 4 does not change production routing and does not deploy anything to Railway.
