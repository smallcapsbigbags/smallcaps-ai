# Jobs UX Pass 5 — Release Acceptance

Pass 5 is the release-candidate gate for the Jobs-style Smallcaps.ai programme. It does not redesign the product. It proves that the product created in Passes 0–4 behaves as one coherent investor journey in CI and production.

## North Star

Smallcaps.ai must answer, with minimal friction:

1. What changed?
2. What is the evidence?
3. What does Smallcaps.ai think it means?
4. What should I watch next?
5. Where can I verify the source?

The public hierarchy remains:

**Verdict → Evidence → Interpretation → Depth**

## Frozen product surfaces

The following presentation layers are frozen unless Pass 5 identifies a release-blocking defect:

- Feed;
- Analyst Note;
- Company Intelligence;
- private-beta entrance;
- semantic impact language;
- typography, spacing and action hierarchy established in Passes 1–3.

The Analyst 3.2 editorial/taxonomy contract established in Pass 4 is also frozen.

## Pass 5 acceptance matrix

### 390px mobile

Covered by `launch-visual-audit`:

- beta entrance;
- Feed;
- Feed primary touch target;
- Analyst Note;
- expanded evidence/calculation table;
- rich Company Intelligence;
- no page-level horizontal overflow.

### 1280px laptop

Covered by `release-acceptance`:

- beta entrance has one primary action;
- Feed verdict/evidence/impact contract;
- original RNS source is a direct HTTP link;
- `Read analysis →` is keyboard reachable with a visible focus indicator;
- Feed → Analyst Note → Company Intelligence navigation works;
- no page-level horizontal overflow;
- no runtime traceback during the journey.

### 1440px desktop

Covered by `launch-visual-audit`:

- beta entrance;
- material Feed records including Trellus, Gamma and Springfield fixtures;
- Analyst Note executive hierarchy and supporting depth;
- Company Intelligence for sparse and rich company histories;
- direct source links and navigation.

## Cross-surface data acceptance

`python -m jobs.release_acceptance --require-public-data` checks the production read path without external calls.

It verifies that:

- production uses PostgreSQL;
- a publishable announcement exists;
- the latest public day can be loaded through the Feed read model;
- public Feed rows retain ticker, headline, takeaway and direct HTTP source provenance;
- a material Feed record resolves to a publishable Analyst Note;
- the same announcement appears in public company history;
- Company Intelligence carries the announcement into its company-memory snapshot;
- Feed and Analyst Note resolve to the same verdict-first presentation contract;
- current Analyst 3.2 rows, when present, use the canonical RNS taxonomy and the code-locked Pass 4 prompt version.

The web Railway deployment now runs this release acceptance after the existing runtime, production-database and publication-safety audits. A web deploy therefore fails before serving traffic if the public read path is broken.

## Data-state warnings that are not release blockers

These remain visible but do not by themselves make the product unsafe to ship:

- an owner-review item that is hidden from public pages;
- no live Analyst 3.2 RNS yet, before the next eligible announcement is analysed;
- no stored price-reaction data yet, while the research surfaces correctly show a pending state.

They become release blockers only if they leak unsafe records publicly or break the investor journey.

## Release blocker definition

Pass 5 must fail if any of the following is true:

- production is not PostgreSQL;
- a publishable record has unavailable/implausibly short evidence;
- a publishable record lacks a usable source link;
- Feed cannot open its Analyst Note;
- Analyst Note cannot connect to Company Intelligence;
- the company history/memory read models lose the selected announcement;
- the public verdict differs between Feed and Note for the same record;
- a current Analyst 3.2 record has non-canonical taxonomy or wrong prompt provenance;
- 390px, 1280px or 1440px layouts clip horizontally;
- the primary mobile action is below the touch-target threshold;
- the primary Feed action cannot be reached by keyboard with visible focus;
- the release journey emits a runtime traceback.

## Final release procedure

1. Run repository tests and deterministic analyst-intelligence benchmarks.
2. Run the 390px/1440px visual workflow.
3. Run the 1280px release-acceptance workflow.
4. Review the generated screenshot artifacts.
5. Merge only when all gates are green.
6. Wait for Railway `smallcaps-ai` and `AIM Ingestion` to reach `SUCCESS` on the merged `main` commit.
7. Confirm Postgres remains healthy and the ingestion cron remains `*/10 6-18 * * 1-5`.
8. Inspect web and ingestion production audit logs for `failure_count: 0` and `runtime_warnings: []`.
9. Freeze Passes 0–5 and move future work to product/analytical roadmap items rather than continued launch redesign.
