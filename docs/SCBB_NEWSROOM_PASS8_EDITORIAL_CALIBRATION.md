# Smallcaps.ai Newsroom Pass 8 — Edition State & Editorial Calibration

Pass 8 turns the Pass 7 one-shot editor into a newsroom that can track how the AIM tape develops through the trading day without adding a ranking LLM or a new Railway service.

## Canonical edition states

- `early_read` — 07:30 Europe/London
- `morning_note` — 08:00 Europe/London
- `aim_close` — 16:35 Europe/London

A custom cutoff remains available for deterministic replay and audit, but the three named states are the publication contract.

## Developing-story identity

Publication-safe FULL analyses receive a persistent `story_key` and `story_family` in PostgreSQL. A new announcement can inherit an existing story key when it belongs to the same company and story family inside a conservative family-specific lookback window.

Examples:

- possible offer → Rule 2.6 deadline → offeror disclosure = one takeover story
- funding warning → refinancing update = one solvency/funding story where the family rules support it
- unrelated trading and board announcements remain separate stories

Story identity is additive. It does not alter Analyst 3.3, Company Memory, the monitoring sheet or the underlying RNS record.

## Owner calibration

The newsroom supports five audited correction actions:

- `lead`
- `promote`
- `demote`
- `suppress`
- `group`

Every correction stores the pre-correction algorithm score, algorithm bucket, story key, reason, owner identity and a structured snapshot. The same correction automatically creates an `editorial_calibration_cases` row so real owner judgement becomes a replayable calibration dataset instead of disappearing into manual edits.

The command-line owner workflow is:

```bash
python -m jobs.editorial_override \
  --date 2026-08-25 \
  --state morning_note \
  --action promote \
  --source-id <source_id> \
  --reason "Why the automatic allocation was wrong"
```

Calibration cases can be exported with:

```bash
python -m jobs.export_editorial_calibration --output /tmp/editorial-calibration.json
```

## Safety

- ARCHIVE and LIGHT records never become editor candidates.
- Review-state analyses remain excluded.
- The ranking remains deterministic.
- Owner changes are explicit overrides; they do not silently alter Analyst 3.3 scores.
- Story-link sync failure degrades the ingestion job but does not discard RNS ingestion.
- No customer-facing UI is introduced in Pass 8.
- Railway topology remains Postgres + smallcaps-ai + AIM Ingestion.
