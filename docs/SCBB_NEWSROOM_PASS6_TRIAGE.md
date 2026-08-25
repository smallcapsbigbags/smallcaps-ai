# Pass 6 — Economical newsroom RNS funnel

## Product rule

> Record everything. Screen everything. Analyse selectively. Publish almost nothing.

Pass 6 changes processing depth, not AIM coverage. Every newly discovered AIM announcement is written to the durable triage ledger before expensive evidence or Analyst 3.3 work begins.

## Three processing levels

### ARCHIVE

For deterministic routine classes such as Total Voting Rights, block-listing returns, routine AGM notices and administrative publications.

- catalogue metadata and provenance are persisted;
- no evidence retrieval is required;
- no Analyst 3.3 call is made;
- the triage record becomes terminal immediately.

### LIGHT

For potentially useful but normally non-thesis-changing events such as director dealings, LTIPs, board changes, holdings and contracts whose materiality is not known from the catalogue title alone.

- exact evidence is retrieved once;
- a small deterministic fact sketch is retained;
- Company Memory supplies narrow context such as latest revenue/share count, recent director dealings and recent adverse trading;
- no LLM decides whether to escalate;
- final LIGHT records become terminal only after evidence has been successfully persisted.

### FULL

For trading/results/guidance, financing/distress, M&A/takeover, major operational/regulatory events and LIGHT announcements that cross an escalation rule.

FULL uses the existing evidence → Analyst 3.3 → Company Memory → quality/publication-safety pipeline unchanged.

## Loss-averse defaults

Unknown catalogue titles default to LIGHT rather than ARCHIVE.

A LIGHT item escalates to FULL when deterministic evidence/context indicates, among other things:

- profit warning, guidance deterioration, solvency/covenant/funding trigger or takeover/strategic-review event;
- CEO/CFO dealing or departure;
- repeated director dealing or a director event after a recent adverse trading disclosure;
- non-senior director transaction of at least £100k;
- contract/order value at least 10% of latest known revenue;
- contract/order value at least £5m when no reliable revenue denominator is stored;
- the existing conservative £2m contract backstop;
- LTIP/options at least 3% of latest known share count;
- explicit dilution of at least 3%;
- large award counts where no reliable share-count denominator exists.

Missing company context therefore causes large borderline events to escalate rather than be suppressed.

## Durable triage ledger

`announcement_triage` stores one record for every discovered catalogue item, including:

- source ID, ticker, company, published time and title;
- RNS type, source URL and source hash;
- triage class and reason;
- processing level and triage version;
- escalation flag and reason;
- status (`recorded`, `complete`, `queued`, `retryable`);
- deterministic LIGHT fact sketch;
- evidence status, evidence URLs and evidence hash.

The ledger is intentionally independent of public AnalystRun rows. ARCHIVE and final LIGHT records can therefore remain part of the complete AIM tape without pretending they received a full analyst note.

## Retry semantics

- `archive + complete` is terminal.
- `light + complete` is terminal only after exact evidence has been stored.
- `full + complete` requires the existing full analyst pipeline to have succeeded.
- `queued` and `retryable` rows remain eligible on later ingestion cycles.
- evidence retrieval, batch preparation, deterministic screen and Analyst 3.3 failures are never silently treated as completed work.

## Compatibility

Pass 6 does not change:

- Analyst 3.3 output for FULL announcements;
- `scbb-monitoring-v1`;
- `scbb-company-v1`;
- Company Memory rules for full publishable analysis;
- publication-safety requirements;
- the SmallcapsBigBags-style frontend;
- Railway topology.

Production remains exactly:

```text
Postgres + smallcaps-ai + AIM Ingestion
```

## Benchmark

Two deterministic case sets are CI-gated:

- `benchmarks/triage_cases.json` — catalogue metadata routing;
- `benchmarks/triage_evidence_cases.json` — evidence/context escalation.

The runner reports classification accuracy plus an estimated reduction in **full Analyst 3.3 calls** relative to a baseline where every benchmark item receives full analysis.

That percentage is deliberately not presented as total OpenAI-cost savings. LIGHT still performs evidence retrieval so materiality/escalation remains evidence-based and fail-safe.

Run locally/CI with:

```text
python -m jobs.run_triage_benchmark \
  --metadata benchmarks/triage_cases.json \
  --evidence benchmarks/triage_evidence_cases.json
```
