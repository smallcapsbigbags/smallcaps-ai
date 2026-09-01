# Launch repair Pass 4 — Company Intelligence

## North star

The page must answer three investor questions in order:

1. What changed in the latest material announcement?
2. Where does the company stand now?
3. What reported evidence supports that view?

## Audit finding

The previous Company Intelligence route was functionally rich but presented as a miniature database. It loaded six overlapping style sheets and three JavaScript presentation layers, used post-render DOM rewriting to replace legacy language, and converted each dataset into a wide table. On a 390px viewport the seeded Springfield record produced a 6,667px page with repeated field labels.

## Pass 4 decision

The route now uses one direct rendering layer and one dedicated visual layer:

- `news.css` for the shared Smallcaps.ai product shell
- `watchlist.css` for shared watchlist controls
- `company-pass4.css` for Company Intelligence only
- `company.js` for the strict `scbb-company-v1` read model and lazy `scbb-monitoring-v1` evidence

The retired launch mutation and journey enhancers are no longer requested by the page.

## Information hierarchy

### Current position

The latest material announcement is the dominant decision surface. It separates:

- what changed
- the Smallcaps.ai view
- guidance state
- balance-sheet position
- market reaction
- materiality
- source and Company News navigation

Supporting facts, before-to-now evidence and disclosure limits remain collapsed until requested.

### What matters now

Guidance, comparable metrics, open management commitments and unresolved questions appear as compact monitoring cards. Empty cards are not rendered, so sparse company records do not invent a monitoring dashboard.

### Evidence trail

Company history is a chronological set of compact announcement records rather than a six-column table. Full evidence is fetched only when an investor opens an item. Dated Company News deep links and source RNS links remain explicit.

## Acceptance criteria

- current position appears first
- sparse records omit `What matters now`
- no legacy database-table layout or mutation layer is loaded
- no horizontal overflow at 390px
- mobile full-page journey remains below 4,500px for the deterministic Springfield fixture
- all primary mobile controls meet a 44px target
- direct and deep-linked evidence expansion works
- no new AI, database, ingestion or market-data feature is introduced
