# Pass 1 Repository and Donor Audit

## Decisions retained

- `smallcapsbigbags/smallcaps-ai` is the production destination.
- `main` remains untouched.
- `build/aim-intelligence-v1` is the protected build branch.
- `smallcapsbigbags/rns-xray` remains a read-only donor/reference repository.
- Existing static prototypes remain preserved as design references.

## Donor map

| RNS-Xray component | Smallcaps.ai treatment |
|---|---|
| strict Pydantic models | ported and extended in `analyst/models.py` |
| analysis guardrails | ported and strengthened in `analyst/guardrails.py` |
| context selector | ported in `analyst/context_selector.py` |
| materiality-first analyst method | adapted into `prompts/ANALYST_ENGINE_V2.md` |
| Investegate Daily AIM source | ported into `ingestion/investegate_daily.py` |
| daily orchestration | adapted to PostgreSQL in `ingestion/daily_service.py` |
| London/Yahoo market logic | ported into `market/pricing.py` |
| daily JSON cache | retired as the system of record |
| old Streamlit presentation | reference only; final Feed/Note UI is later work |

## Locked Daily AIM path

```text
Investegate AIM catalogue
  → deterministic catalogue metadata
  → PostgreSQL source-ID deduplication
  → routine classification / material prioritisation
  → OpenAI web-search evidence retrieval for selected new RNSs
  → point-in-time company context
  → Analyst Engine 2.0
  → deterministic guardrails
  → publication-quality gate
  → versioned PostgreSQL
```

Manual ingestion remains for QA and recovery.

The full corrective audit is recorded in
`docs/PASS-1-AUDIT-RESULTS.md`; Pass 2 is specified in
`docs/PASS-2-ANALYST-ENGINE.md`.
