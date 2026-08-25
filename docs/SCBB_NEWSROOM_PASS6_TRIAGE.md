# Pass 6 — Economical newsroom RNS funnel

## Product rule

> Record everything. Screen everything. Analyse selectively. Publish almost nothing.

Pass 6 changes processing depth, not AIM coverage. Every newly discovered AIM announcement is persisted before expensive work starts. The RNS catalogue metadata and provenance remain available even when no full Analyst 3.3 note is created.

## Three processing levels

### ARCHIVE

For deterministic routine classes such as Total Voting Rights, block-listing returns, routine AGM notices and administrative publications.

- catalogue metadata and provenance are persisted;
- a deterministic low-impact compatibility note keeps existing ALL RNS/public read models stable where appropriate;
- no deep evidence retrieval is required;
- no Analyst 3.3 call is made.

### LIGHT

For potentially useful but normally non-thesis-changing events such as director dealings, LTIPs, board changes, holdings and contracts whose materiality is not known from the catalogue title alone.

- exact evidence is retrieved once;
- simple money/percentage/security facts are extracted deterministically;
- Company Memory supplies narrow context such as latest revenue/share count, recent director dealings and recent adverse trading;
- no LLM decides whether to escalate;
- final LIGHT rows do not receive a full Analyst 3.3 note.

### FULL

For trading/results/guidance, financing/distress, M&A/takeover, major operational/regulatory events and LIGHT announcements that cross an escalation rule.

FULL uses the existing evidence → Analyst 3.3 → Company Memory → quality/publication-safety pipeline unchanged.

## Fail-safe defaults

Unknown catalogue titles default to LIGHT rather than ARCHIVE.

A LIGHT item escalates to FULL when deterministic evidence/context indicates, among other things:

- a profit warning, guidance cut, solvency/covenant/funding trigger or takeover/strategic-review event;
- CEO/CFO dealing or departure;
- repeated director dealing or a director event after adverse trading;
- director transaction of at least £100k;
- contract/order value at least 10% of latest known revenue;
- contract/order value at least £5m when no reliable revenue denominator exists;
- unusually material company language such as `transformational`;
- LTIP/options at least 3% of latest known share count;
- large award counts where no reliable share-count denominator exists.

The rules are intentionally conservative. Missing company context causes large borderline events to escalate rather than be suppressed.

## Persistence

`announcement_triage` stores one durable triage record per announcement:

- `triage_class`
- `triage_reason`
- `processing_level`
- `triage_version`
- `metadata_score`
- `escalated`
- `escalation_reason`
- `light_facts`
- `source_hash`
- `evidence_hash`

`announcements` remains the canonical source record.

A metadata-only FULL row is deliberately not terminal. It remains retryable until a current AnalystRun exists. A LIGHT row is terminal only after retrieved evidence has been persisted (`evidence_hash` is non-empty). This prevents evidence/batch/screening failures from being silently treated as completed work.

## Compatibility

No changes are made to:

- Analyst 3.3 output for FULL announcements;
- `scbb-monitoring-v1`;
- `scbb-company-v1`;
- Company Memory logic for full publishable analysis;
- public publication-safety requirements;
- Railway topology.

The production architecture remains exactly:

```text
Postgres + smallcaps-ai + AIM Ingestion
```

## Benchmark

`benchmarks/triage_cases.json` covers routine, ambiguous and clearly material metadata plus evidence-level escalation cases for director dealing, contract scale, LTIP dilution, senior-management departures and hidden solvency events.

CI runs:

```text
python -m jobs.run_triage_benchmark --cases benchmarks/triage_cases.json
```

The benchmark reports both classification accuracy and an estimated reduction in full Analyst calls relative to a baseline in which every non-ARCHIVE/ambiguous case receives a full analysis.

This is a model-call proxy, not a total OpenAI-cost estimate: LIGHT still performs evidence retrieval so that escalation remains evidence-based and fail-safe.
