# Smallcaps.ai Phase 2 Gold-Standard Rubric

This rubric is derived from the paid human daily analyst reports reviewed during Phase 2. The goal is not to copy their prose or their page layout. The goal is to match the underlying analyst behaviour: filter the noise, identify the economically important facts, compare them with prior expectations, do the useful maths, explain the consequences, and say what still needs proving.

## Acceptance standard

Each material RNS is scored out of 100. A case passes only when:

- total score is at least 82/100;
- factual grounding is at least 16/20;
- there is no critical factual error, invented number, invented comparator or invented legal conclusion;
- explicit adverse disclosures are not buried;
- reported facts, Smallcaps.ai calculations and Smallcaps.ai interpretation remain visibly separate;
- the deterministic publication-quality gate does not block or hold the note for review.

Phase 2 is ready to close when the locked 20-case real-RNS benchmark achieves:

- average score at least 85/100;
- no scored case below 75/100;
- average factual-grounding score at least 18/20;
- no critical provenance or hallucination failures;
- at least 18/20 cases correctly identify the main investment-relevant change;
- all 20 outputs are `publishable` under the production quality gate;
- no case has the wrong Impact direction, and at least 18/20 are judged fully aligned on Impact direction/significance.

The same 20 cases remain locked during improvement work. We do not replace hard cases to raise the score.

## 100-point scoring rubric

### 1. Factual grounding and provenance — 20 points

The note must preserve the announcement's important facts, numbers, periods and qualifiers. Reported, calculated and inferred content must not be blurred.

Full marks require:
- no invented figures or unsupported conclusions;
- important reported numbers reproduced accurately;
- calculations based only on visible verified inputs;
- uncertainty preserved where the source is uncertain;
- no later information or share-price reaction used to rewrite the fundamental judgement.

Critical failure: invented number, invented comparator, materially wrong fact, or an inference presented as company-reported fact.

### 2. Investor relevance and ranking — 10 points

The note must lead with what is most capable of changing an investor's assessment, not with the company's preferred wording.

Full marks require:
- the headline captures the real economic change;
- the top two or three facts are the ones an investor would actually care about;
- adverse facts are not buried below PR language;
- routine detail is compressed.

### 3. Comparator discipline / What Changed — 12 points

A strong analyst asks `versus what?`.

Full marks require:
- latest explicit company guidance used before weaker comparators;
- latest relevant prior disclosure used where available;
- prior-period comparisons identified correctly;
- today's information separated from already-known information;
- a small beat after a large prior upgrade is treated as a small new change, not a fresh major upgrade.

### 4. Useful calculations and auditability — 10 points

Smallcaps.ai should do simple maths that saves the investor time when the inputs are verified.

Examples include:
- dilution;
- percentage change;
- margin movement;
- ownership change;
- offer premium;
- acquisition price / disclosed target revenue or profit;
- contract size relative to verified revenue;
- debt reduction;
- simple operating leverage or cash-return arithmetic.

Full marks require every calculation to show enough inputs to reproduce it. Do not calculate when the denominator or accounting basis is unreliable.

### 5. Commercial and causal interpretation — 10 points

Do not stop at `revenue up 20%` or `profit down 15%`.

Full marks require the note to ask, where evidence allows:
- why did the number change?;
- volume, price, mix, acquisition, FX, timing, cost reduction or one-off?;
- did profit growth convert to cash?;
- did debt fall from operations, a placing or an asset sale?;
- is a contract economically material or merely impressive-sounding?;
- is a profit improvement operational or accounting-driven?

### 6. Sector- and event-specific KPI selection — 8 points

The analyst must identify the metric that matters for the type of business or event rather than treating headline revenue as universally important.

Examples:
- recruiter: net fee income, conversion, consultant productivity;
- lender: loan book, tangible equity, ROE, cost of risk;
- housebuilder/property: net debt/cash, NAV, land sales, completions, margin;
- software: ARR/recurring revenue, retention, margin;
- contractor: order book, margin, cash conversion;
- resources: production, realised price, AISC/costs, capex;
- acquisition: consideration, target economics, funding, leverage, dilution;
- takeover: offer price, premium, support, approvals, completion conditions.

### 7. Balance sheet, capital and control lens — 8 points

For small caps, the note should automatically ask whether the announcement changes financial risk or shareholder economics.

Where relevant, cover:
- cash and net debt;
- covenant/funding headroom;
- working-capital pressure;
- dilution;
- buybacks and capital returns;
- financing source for acquisitions;
- control/ownership mechanics such as Rule 9 or concert parties.

Award full marks when the lens is applied only where relevant rather than forced into every note.

### 8. Uncertainty, disclosure gaps and complex concepts — 6 points

Full marks require:
- important missing information stated plainly;
- uncertainty not converted into fake precision;
- specialist concepts explained when they are necessary to understand the RNS;
- legal/regulatory wording translated into normal English without inventing legal conclusions.

Examples include Rule 9, covenant waivers, concert parties, reverse takeovers, CLNs, earn-outs and unusual voting-rights mechanics.

### 9. Investment-case change — 6 points

The note should make clear whether today's new evidence:
- strengthens the case;
- weakens the case;
- leaves it broadly unchanged; or
- remains unclear.

This is not a Buy/Sell/Hold recommendation. It is an assessment of whether today's evidence changes the investment case.

### 10. Repeatability and what comes next — 5 points

A strong analyst asks whether the improvement or deterioration is repeatable.

Full marks require:
- temporary/timing effects distinguished from structural change where evidence allows;
- the next measurable proof point identified;
- watch items are specific rather than generic.

### 11. Plain English and scanability — 5 points

The reader should not need to translate broker, legal or corporate language.

Full marks require:
- headline understandable in one read;
- short direct sentences;
- concrete numbers before adjectives;
- technical terms explained only when needed;
- no PR boilerplate;
- depth proportional to importance.

## Non-scored mandatory rules

- Impact and market reaction remain analytically separate.
- A falling share price does not make an RNS red.
- The analyst may discuss a market reaction only as an observation, not as evidence that the fundamental analysis was right or wrong.
- No Buy/Sell/Hold recommendation, price target or fair value.
- No broker consensus invented from context.
- No criticism manufactured merely to sound sceptical.

## Human-report behaviours this benchmark is designed to reproduce

The reference reports repeatedly demonstrate these behaviours:

- compress most announcements, deepen only the important ones;
- compare today's number with the latest guidance, not just last year;
- identify the economically meaningful KPI for the business;
- explain why a number changed and whether the driver is repeatable;
- use simple calculations to expose dilution, premiums, margins and transaction economics;
- keep balance-sheet risk visible;
- challenge management framing without forcing a bearish conclusion;
- distinguish a company-specific problem from an external or temporary factor;
- revisit an earlier view when new evidence genuinely changes it;
- say `we do not know yet` when the source does not support a firm conclusion.
