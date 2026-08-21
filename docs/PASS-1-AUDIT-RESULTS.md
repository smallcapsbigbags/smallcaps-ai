# Pass 1 Audit Results

**Audited branch:** `build/aim-intelligence-v1`  
**Audit outcome:** Foundation accepted after the corrective work below.

## Executive assessment

Pass 1 established the right boundaries: deterministic AIM catalogue discovery, OpenAI evidence retrieval, strict structured analysis, deterministic guardrails, versioned PostgreSQL persistence and separate market-reaction logic.

The audit found no reason to redesign the architecture. It did find several publication-integrity and provenance gaps that needed correction before the Analyst Engine could be treated as production-capable.

## Findings and resolution

| Severity | Finding | Resolution |
|---|---|---|
| Critical | Evidence retrieval could return no usable text, then continue with a headline-only fallback and persist an analysis. | Deep analysis now raises `EvidenceUnavailableError`; the item remains unpersisted and retryable. |
| High | Guardrail warnings were attached to an Analyst Note but did not prevent persistence. | Added a deterministic quality gate. Guardrail failures now block persistence. |
| High | Source-retrieval notes were appended to the evidence text, mixing provenance with the source dossier. | Added separate `source_note`, `source_urls`, `evidence_status` and retrieval timestamp fields. |
| High | `schema.sql` enforced one current analyst run, but the SQLAlchemy model used by `create_all()` did not. | Added a dialect-aware unique partial index to the ORM model. |
| High | The Pass 1 prompt was too general for contracts, financing, M&A, takeovers, ownership, remuneration and operational announcements. | Replaced it with Analyst Engine 2.0 and event-specific equity-analysis rules. |
| Medium | Impact had a colour and score but no explicit structured rationale or driver decomposition. | Added `impact_rationale` and structured `impact_drivers`. |
| Medium | Disclosure quality and material missing information were not first-class outputs. | Added `disclosure_assessment`. |
| Medium | Fact comparators lacked source identity and numerical normalisation fields. | Added comparator type/source, numeric value/range, currency and as-of date. |
| Medium | Guidance and management claims lacked enough structure for future ledgers. | Added prior guidance source/value and claim keys/metrics/targets. |
| Medium | The operator console had a reserved password variable but no access gate. | Added constant-time password checking when `APP_ADMIN_PASSWORD` is set. |
| Medium | No repeatable difficult-announcement evaluation set existed. | Added 16 canonical benchmark cases, evaluator and live benchmark runner. |
| Low | Manual source URLs were not carried into a source-reference list. | Manual ingestion now preserves source URLs and retrieval metadata. |

## Quality-state behaviour

- `publishable`: no deterministic issue requires intervention.
- `review`: analysis may be stored but must be reviewed before public display.
- `blocked`: evidence or analytical integrity is insufficient; the announcement is not persisted and remains retryable.

The public Feed must only display `publishable` records until the owner-review workflow is built.

## Accepted foundation

The following Pass 1 decisions remain unchanged:

- `smallcaps-ai` is the production destination.
- `rns-xray` remains the donor/reference repository.
- Investegate identifies the exact AIM catalogue rows.
- OpenAI web search retrieves evidence only after discovery and deduplication.
- PostgreSQL is the system of record.
- Raw price reaction never changes the original AI Impact.
- No historical AIM backfill or Company Intelligence UI is introduced in V1.


## Accepted production-hardening deferrals

These are not Pass 2 blockers, but remain explicit before public launch:

- database migrations are not yet managed by Alembic; the feature branch currently assumes a fresh Railway database;
- the daily worker assumes one active scheduler instance; distributed worker locking is deferred;
- blocked/retry attempts are reported in worker logs rather than stored in a dedicated ingestion-attempt table;
- a credentialled live Investegate/OpenAI/PostgreSQL smoke test still requires the owner’s Railway variables;
- RNS and market-data commercial rights remain separate launch dependencies.
