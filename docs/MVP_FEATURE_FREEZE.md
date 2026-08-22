# Smallcaps.ai MVP Feature Freeze

## Decision

The MVP feature set is frozen for the two-day launch programme.

From this point until launch, work is admitted only when it answers **yes** to one of these questions:

1. Does the issue prevent a real AIM RNS from reaching the Feed?
2. Could it publish materially unsupported or misleading analysis?
3. Does it prevent a normal investor from opening and understanding the product?
4. Could it lose, duplicate or corrupt the production research record?
5. Does it prevent the production services from building, starting or running on schedule?

Everything else is post-launch work.

## Locked MVP

### Customer product

- password-protected private-beta access;
- daily AIM Intelligence Feed;
- search, date and Impact ordering;
- plain-English Feed cards;
- full Analyst Note;
- original RNS links;
- Company Intelligence page and RNS timeline;
- lightweight local watchlist behaviour;
- available event-day market reaction.

### Analyst system

- evidence-bound RNS retrieval;
- Analyst 3.1 plain-English analysis;
- reported / calculated / Smallcaps.ai-view separation;
- useful calculations with visible inputs;
- specialist-concept explanations;
- Impact colour and score;
- point-in-time Company Memory;
- guidance and management-claim tracking;
- sector-specific KPI checklist;
- deterministic contradiction checks;
- final consistency review;
- fail-closed guardrails and quality review queue.

### Operations

- PostgreSQL as the production source of truth;
- versioned analyst runs rather than destructive overwrites;
- Investegate discovery and source-ID deduplication;
- scheduled AIM ingestion;
- scheduled market-reaction collection;
- PostgreSQL advisory locks;
- persistent job status;
- runtime validation before Railway starts a service;
- GitHub Actions compilation, PostgreSQL and regression tests.

## Version freeze

```text
Analyst version: aim-intelligence-analyst-3.1
Prompt version:  analyst-engine-3.1-sector-intelligence
```

Railway production uses the prompt version shipped in `analyst/version.py`. A stale `PROMPT_VERSION` environment variable is ignored for production metadata.

## Explicitly deferred

These are not launch blockers:

- full historical AIM backfill;
- broker estimates or consensus;
- intrinsic valuation and price targets;
- Buy / Sell / Hold recommendations;
- persistent user accounts;
- email, SMS or push alerts;
- portfolio accounting;
- advanced screening;
- user-authored research notes;
- automatic semantic reconciliation of every differently named KPI;
- automatic reconstruction of missed historic closing prices;
- +1 / +5 / +20-day market returns;
- a complete Management Delivery Engine beyond the claim tracking already present;
- additional sector templates unless a real launch case demonstrates a material failure;
- redesign work that does not fix a usability defect.

## Remaining launch passes

### Pro Pass 1 — Finish and freeze

- merge Analyst 3.1 into `main`;
- confirm CI is green;
- confirm code versions and runtime configuration are aligned;
- allow Railway production deployments to complete;
- create the launch-blocker list only.

### Pro Pass 2 — Production operation

- verify web, ingestion, database and price services;
- run real RNSs end to end;
- verify review, retry and duplicate behaviour;
- fix only operational or analytical launch blockers.

### Pro Pass 3 — Customer launch audit

- desktop and mobile usability;
- navigation and source links;
- empty, loading and error states;
- first-user comprehension;
- final GO / NO-GO checklist.

## Launch rule

A limitation can be disclosed. A broken core workflow cannot.

The MVP launches when a normal investor can open Smallcaps.ai, see a current AIM announcement, understand what changed and why it matters, open the original RNS, and inspect the company's accumulated record without assistance.
