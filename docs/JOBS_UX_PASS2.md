# Smallcaps.ai Jobs UX Direction — Pass 2

**Date:** 23 August 2026  
**Base:** final Pass 1 Feed on `main`

## Objective

Pass 2 turns the Analyst Note from a long generated report into an edited equity-research surface whose first screen answers the investor's real questions.

The hierarchy is:

> **Verdict → What happened → Evidence → Our view → What to watch → Supporting detail**

The Feed is frozen during this pass. PostgreSQL, ingestion, Analyst 3.1, Company Memory and the stored research schema are unchanged.

## Executive layer

The expanded Analyst Note must make the following visible before optional depth:

1. Quiet navigation: Feed, Company and Original RNS.
2. Company metadata and semantic impact signal.
3. Outcome-led verdict headline.
4. **What happened** — concise event explanation.
5. **Evidence from the RNS** — up to three decision-useful facts.
6. **Our view** — clearly attributed Smallcaps.ai judgement.
7. **What to watch** — only when there are specific measurable watch items.

The executive layer uses the same conservative verdict and evidence-editing rules as the final Feed so the user does not encounter two different editorial languages for the same event.

## Progressive disclosure

Secondary analysis remains available but does not compete with the executive layer. It is placed behind restrained expanders:

- What changed;
- Full evidence & calculations;
- Investment case detail;
- Guidance;
- Disclosure & terminology;
- Market reaction.

An expander is rendered only when it contains real information.

## Empty-state rule

The note must not display generated filler such as:

- `No new supporting evidence identified.`
- `No new challenge identified.`
- `No genuine guidance change identified.`
- `No specific watch item identified.`
- pending market-reaction copy when no valid price exists.

Absence is silent unless the absence itself is decision-useful and is explicitly captured by the analyst as a disclosure gap.

## Navigation rule

The top of the note contains the only main navigation row:

- `← Feed`
- `Company`
- `Original RNS ↗`

The old duplicated bottom action row is removed.

## Evidence and provenance

- Reported evidence is grouped under `Evidence from the RNS`; `Reported` is not repeated under each item.
- Calculated evidence remains explicitly marked `Smallcaps.ai calculation`.
- Narrative evidence uses the primary sans-serif typography; compact numerical evidence may use monospace.
- Meaningless comparator placeholders are suppressed while genuine prior values remain visible.
- `Our view` carries a visible provenance line stating that it is Smallcaps.ai analysis, not company-reported fact.

## Mobile acceptance

At 390px:

- the executive evidence grid collapses to one column;
- quiet navigation wraps without page overflow;
- the verdict and primary explanation remain readable without horizontal clipping;
- expanded supporting tables remain responsive;
- internal navigation begins at the top of the target page.

## Automated acceptance gate

Pass 2 is complete only when:

- the complete repository test workflow passes;
- the visual journey passes on desktop and 390px mobile;
- Trellus displays the final outcome-led verdict in the Analyst Note;
- `What happened`, `Evidence from the RNS`, `Our view`, `What to watch` and `Supporting detail` appear in that order;
- the Original RNS remains directly accessible;
- no legacy empty-section filler is visible;
- supporting evidence is collapsed by default;
- expanded evidence tables do not clip on desktop or mobile;
- Feed → Note → Company navigation still starts at the top;
- all RNS, database and analyst text remains HTML-escaped.

## Pass 2 completion rule

Once these checks pass against the deterministic Trellus case and production deploys cleanly, the Analyst Note is frozen for the Jobs UX programme. The next surface is Company Intelligence and the private-beta entrance in Pass 3.
