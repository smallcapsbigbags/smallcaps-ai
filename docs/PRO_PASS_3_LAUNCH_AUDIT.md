# Pro Pass 3 — Customer Launch Audit

Date: 22 August 2026

## Objective

Pro Pass 3 is the final customer-facing pass for the frozen Smallcaps.ai MVP. It does not add another analyst feature. It asks one question:

> Can a normal AIM investor open the product, understand what changed and why it matters, inspect the original RNS and move through the company record without assistance?

## Customer journey under test

```text
Private beta access
  → latest available AIM Intelligence Feed
  → full Analyst Note
  → Company Intelligence
  → original RNS
```

## Launch fixes completed

### First visit

- The private-beta screen now explains the product before asking for a code.
- The three evidence types are introduced in plain English: Reported, Calculated and Smallcaps.ai view.
- The access screen contains the same visual system as the product.

### Feed

- The Feed opens on the latest date containing publishable analysis rather than an empty weekend or bank-holiday date.
- Empty results distinguish between an empty market date, an active filter and an empty watchlist.
- Users can return to the latest available date or clear filters directly from the empty state.
- Impact now exposes both magnitude and direction in text, for example `IMPACT HIGH · GREEN`, rather than relying on colour alone.
- A missing market observation no longer appears as an unexplained dash.
- Feed actions use shorter mobile-safe labels while retaining Analysis, Company Intelligence, watchlist and original-RNS access.

### Analyst Note

- Feed, Company and original-RNS navigation is available at the top of the note.
- Key-number, guidance and market-reaction tables become labelled stacked records on narrow screens.
- Source URLs are accepted only when they use HTTP or HTTPS.
- Missing market reaction is explained as pending rather than presented as a result.
- The note retains the distinction between company-reported facts, Smallcaps.ai calculations and Smallcaps.ai interpretation.

### Company Intelligence

- The current hierarchy now starts with the latest Smallcaps.ai view before the historical tables.
- Coverage-building language is shorter and explicit about what is and is not known.
- The page retains current guidance, comparable KPI series, management promises, disclosure gaps and the RNS timeline.
- Latest and timeline source links are validated before rendering.

### Reliability and publication safety

- Public configuration and database failures now produce a plain service message rather than a raw traceback.
- Full exception detail is written to Railway logs with a reference code.
- A deterministic startup/pre-deploy check moves unsafe legacy records to the owner review queue when evidence is unavailable, evidence text is implausibly short, or no usable original source URL remains.
- The safety reconciliation never deletes research or changes a reported fact. It changes only public eligibility, appends a quality flag and records a correction audit row.
- The production audit runs again after reconciliation.

### Disclosure

Every customer page now carries the same plain-English footer:

> Smallcaps.ai can make mistakes. Check the original RNS before acting. This is research support, not personal investment advice.

## Automated acceptance gate

The merge gate requires:

- complete Python compilation;
- complete repository test suite;
- PostgreSQL integration;
- Analyst Intelligence signal benchmark;
- Analyst Intelligence false-positive controls;
- Railway JSON validation;
- publication-safety tests;
- latest-publishable-date test;
- mobile and source-link helper tests.

## Final live checks

A Saturday deployment can prove the web application, private-beta gate, PostgreSQL, existing Feed, Analyst Notes, Company Intelligence and source links.

The first genuine post-release market-session check is Monday 24 August 2026:

1. a new AIM announcement is discovered without manual intervention;
2. evidence is retrieved;
3. Analyst 3.1 writes a current versioned record;
4. publishable analysis appears on the Feed;
5. rerunning discovery does not duplicate the record;
6. a valid event-session price appears when market data is available;
7. any review-required item stays out of public pages.

## GO / NO-GO rule

### GO — private beta

Launch when:

- web and ingestion deployments are successful;
- the beta gate works;
- the latest available Feed contains at least one publishable record;
- a Feed item opens its Analyst Note and Company Intelligence page;
- the original RNS link opens;
- no unsafe record remains public;
- the mobile layout is readable;
- the owner can reach the review queue.

### NO-GO

Do not invite beta users when:

- the web service cannot start;
- PostgreSQL is unavailable or read-only;
- current records can duplicate;
- a public note lacks a usable source link;
- unavailable evidence can remain publishable;
- the beta password is not configured;
- a normal user encounters a raw exception.

## Explicitly outside this launch gate

- full historical AIM backfill;
- broker estimates;
- price targets or Buy/Sell/Hold recommendations;
- persistent user accounts;
- email, SMS or push alerts;
- portfolio accounting;
- advanced screening;
- automatic recovery of every missed historical market close;
- +1 / +5 / +20-day returns;
- a public paid launch before the owner has confirmed the required RNS and market-data rights.
