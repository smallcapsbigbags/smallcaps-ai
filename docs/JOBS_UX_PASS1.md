# Smallcaps.ai Jobs UX Direction — Pass 1

**Date:** 23 August 2026  
**Base commit:** `c7147b80a7d09be3c80b7732b649667875276d39`  
**Working branch:** `ux/jobs-pass-1`

## Objective

Audit the merged Pass 0 safety baseline, correct any residual defects, then rebuild the AIM Feed around the product hierarchy:

> **Verdict → Evidence → Smallcaps.ai view → Depth**

Pass 1 changes shared presentation primitives and the Feed only. The Analyst Note, Company Intelligence data model, PostgreSQL schema, ingestion system, Analyst 3.1 and Railway topology remain frozen.

## Pass 0 audit

### Correctly completed

- Public exceptions receive customer-safe `WEB-XXXXXXXX` references.
- Full tracebacks remain in application logs.
- Incident references are escaped before public rendering.
- Semantic impact language is implemented independently of storage colour.
- A deterministic desktop/mobile screenshot baseline is retained.
- Railway production contains only PostgreSQL, Smallcaps.ai and AIM Ingestion.

### Residual issues found and corrected

1. **The visual workflow did not run after direct pushes to `main`.**  
   It still watched the retired `launch/pro-pass-3` branch. Pass 1 changes the push gate to `main`, while retaining pull-request and manual execution.

2. **The exception logger could still fail while trying to print a traceback.**  
   Logging is now best-effort: a reference is always returned even if output or traceback logging itself fails. Exception summaries are collapsed to one line and capped at 500 characters to prevent accidental log-line injection.

3. **Semantic impact labels accepted arbitrary level strings.**  
   Impact colour and level are now normalised against the allowed public contract before rendering.

4. **The semantic mapping existed but the public badge still exposed `RED`, `GREEN`, `AMBER` and `GREY`.**  
   The shared badge now renders accessible signals such as `CRITICAL · ADVERSE`, while retaining the colour dot as a redundant visual cue.

5. **The typography still depended on Google Fonts.**  
   The application now uses a native system sans-serif stack and system monospace for numerical data, removing an external render dependency and reducing layout shift.

## Pass 1 Feed contract

### Header and controls

- Retain the AIM Intelligence product title.
- Explain the proposition in one line: every announcement, the change, the evidence and the Smallcaps.ai view.
- Retain date, search, scope and ordering without allowing controls to dominate the page.
- Replace technical `publishable records` language with `analysed announcements`.

### Material announcement hierarchy

1. Quiet ticker, company, useful category and time.
2. Accessible impact signal and available event-session price.
3. Dominant outcome-led verdict.
4. Concise explanation of what happened and why it matters.
5. One Evidence section containing up to three decision-useful facts.
6. A visually distinct Smallcaps.ai view.
7. One dominant `Read analysis →` action.
8. Quiet Company, Original RNS and Watch controls.

### Evidence rules

- `Reported` is not repeated beneath every fact.
- A calculated fact is explicitly marked `Smallcaps.ai calculation`.
- Labels precede values.
- Numerical values use monospace only when the structured fact is genuinely compact data.
- Narrative evidence remains in the primary sans-serif typeface.
- Previous values and comparators remain visible when supplied.

### Routine announcements

- Score-1 records remain available.
- Under the default Most Impactful ordering they move into a collapsed `Routine announcements` section.
- Search results automatically expand that section when routine records match.
- Latest ordering preserves chronological access and uses a compact routine row.

### Mobile rules

- Narrative evidence collapses to one column.
- The primary action is at least 44 pixels high and occupies the full first row.
- Secondary actions wrap beneath it.
- No page-level horizontal overflow is permitted at 390 pixels.

## Deterministic acceptance cases

The visual preview now includes:

- **Trellus Health:** critical adverse administration and no-recovery case with narrative evidence and fallback type `Other`;
- **Gamma Communications:** high mixed preliminary possible-offer case with no disclosed bid price and fallback type `Other`;
- **Springfield Properties:** high favourable buyback case with reported and calculated numerical evidence;
- **AMCO Services:** adverse trading-quality case;
- **Knights Group:** favourable acquisition case;
- **Routine Holdings:** low routine voting-rights record.

The preview cases test the presentation contract; they do not alter production research.

## Automated acceptance gate

Pass 1 is complete only when:

- the full repository test workflow passes;
- the visual journey passes on desktop and 390-pixel mobile;
- Trellus, Gamma and Springfield are all present in the deterministic Feed;
- the public Feed contains semantic impact language and no visible colour-token labels;
- fallback type `Other` is not visible;
- reported evidence is not repeatedly labelled;
- routine announcements are grouped under the default sort;
- the mobile primary action measures at least 44 pixels;
- narrative evidence renders as one mobile column;
- no page-level horizontal overflow occurs;
- Feed → Analyst Note → Company Intelligence navigation still begins at the top;
- source links and HTML escaping remain intact.
