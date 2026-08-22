# Smallcaps.ai — Benchmark-Driven Failure-Mode Overrides

These rules override softer stylistic preferences when they apply. They are deliberately narrow fixes for repeated failures found in the locked 20-case Phase 2 benchmark.

## 1. Revenue growth must never hide deteriorating economics

For results/trading updates, when comparable current and prior revenue plus EBITDA/profit are supplied:

1. compare revenue growth with EBITDA/profit growth;
2. calculate the relevant current and prior margin when the inputs support it;
3. calculate the percentage-point margin change;
4. if revenue grows materially faster than EBITDA/profit and margin falls, surface the margin deterioration in the headline or takeaway unless another issue is clearly more important;
5. do not assign `green` merely because revenue, absolute EBITDA/profit or net debt improved when the economically important new change is a material deterioration in margin/earnings quality.

Example discipline: revenue +33% and EBITDA +9% is not simply a strong growth update. Calculate the margin before deciding direction.

## 2. Loss-making life sciences: cash and funding first

When a biotech/medtech/life-sciences company remains loss-making or cash-consuming:

- headline revenue growth is secondary to cash, operating loss/cash burn and funding runway;
- milestone, royalty or other non-recurring income must not be treated as proof of sustainable profitability;
- if a safe runway calculation cannot be made from comparable disclosed cash-burn inputs, explicitly say `funding runway cannot be safely calculated from the disclosed figures`;
- if funding runway remains uncertain, do not use `green` solely because revenue grew or management expects profitability later;
- `green` requires genuinely favourable new evidence on funding/cash runway, a major de-risking commercial/regulatory event with clear economics, or another similarly strong supported development.

## 3. Earnings downgrades are adverse

If today's announcement clearly reduces a previous explicit profit/earnings expectation:

- call the change an earnings downgrade in plain English;
- if the announcement itself or supplied evidence explicitly describes it as a profit warning, use the phrase `profit warning` prominently;
- Impact should normally be `red`, score 3 or 4 depending on magnitude;
- do not soften the direction to amber because revenue grew, property/assets provide support, or the balance sheet remains manageable unless the same announcement contains genuinely material offsetting new information.

## 4. New information outranks known risk

When prior context contains an existing risk and today's RNS mainly adds new operating evidence:

- lead with what changed today;
- keep the already-known risk as context or an offset unless today's RNS changes that risk;
- do not let a known financing concern dominate a trading update if the main new evidence is improving or worsening continuing operations.

In `analyst_view`, explicitly state whether TODAY'S new evidence strengthens, weakens, leaves unchanged or leaves unclear the investment case after considering the known risk.

## 5. Signed contracts: distinguish modest value from no value

For a newly signed contract with a disclosed non-trivial value:

- if it clearly adds future work/revenue and no major adverse condition is disclosed, direction should usually be favourable even if significance is only low/medium;
- missing margin, customer name or scale can reduce confidence/significance, but should not automatically make the direction grey;
- a routine extension with no disclosed value/economic contribution and no forecast effect can remain grey/low.

Always lead with exact value, duration/timing and what economics are missing.

## 6. Use only the safest obvious calculations

Before writing, choose the 1–3 calculations with the highest investor value. Prefer direct arithmetic over elaborate scenario modelling.

Priority examples:
- EBITDA/profit margin and margin movement;
- guidance midpoint change;
- beat/miss versus latest guidance;
- buyback tranche / issued shares and maximum authority / issued shares;
- acquisition consideration / matched acquired revenue or matched acquired profit;
- upfront consideration / total consideration and deferred amount;
- sale at 92% of book = 8% discount;
- NPV increase versus directly comparable prior NPV;
- contract total / years as rough annual average, clearly not revenue guidance;
- contract total / verified annual revenue;
- implied H2 profit required to reach a stated FY floor, only when accounting basis is consistent.

Do NOT add a calculation if:
- it requires a back-solved denominator that is not necessary;
- numerator and denominator refer to different acquisition perimeters or accounting bases;
- the result adds detail without changing investor understanding;
- source figures appear internally inconsistent.

If source mechanics are inconsistent, flag the inconsistency instead of forcing a scenario calculation.

## 7. Acquisition denominator matching is mandatory

Never divide purchase consideration by a target profit/revenue figure unless the disclosed denominator covers the same acquired business perimeter.

If an acquisition buys roughly 70% of a firm's revenue but only whole-firm LLP profit is disclosed:
- you may calculate consideration / matched acquired revenue if acquired revenue is explicitly disclosed;
- do not present consideration / whole-firm profit as a clean transaction multiple;
- explain that the profit denominator does not match the acquired perimeter and therefore a reliable price/profit multiple cannot be calculated.

## 8. Buyback / Rule 9 calculations stay simple

For buyback and Rule 9 cases:
- calculate initial proposed shares / current issued shares if both are disclosed;
- calculate maximum authority / current issued shares if both are disclosed;
- do not calculate hypothetical future Concert Party ownership unless the full post-buyback denominator and treatment of options/treasury shares are clean and internally consistent;
- if the RNS itself gives future ownership scenarios, report those as reported facts rather than rebuilding them unnecessarily;
- explain that Rule 9 waiver mechanics do not by themselves indicate a takeover.

## 9. Conditional wind-down progress is not automatically high Impact

For property wind-down/disposal updates:
- completed asset sales/cash receipts are facts;
- expected future debt repayment or capital returns remain conditional until completed;
- straightforward progress toward an already-known wind-down plan is usually low/medium significance unless today's RNS materially changes realised value, timing or certainty;
- calculate sale discount/premium to book when directly disclosed.

## 10. Comparator metadata hygiene

A comparator is `prior-disclosure` only when it truly comes from eligible prior company context. Do not label another figure from the same current RNS as a prior disclosure.

For a calculation using two current-RNS inputs, leave `comparator_source_id` blank unless an actual prior source supports the comparator. Do not invent a source ID to make a calculation look contextual.

## 11. Sentence discipline

Public prose should normally use sentences under 30 words. Complex takeover/acquisition/life-science notes are not exempt. Split cause, consequence and uncertainty into separate sentences rather than chaining them.

## Final override check

Before returning, ask privately:
- Is there a revenue/profit/margin contradiction I have not surfaced?
- Is this loss-making life-sciences note putting cash/runway before revenue?
- Did a real earnings downgrade remain red?
- Am I letting an old risk obscure today's new information?
- Did I turn a modest but real contract into grey simply because margin is missing?
- Are my calculations the simplest useful ones with matched denominators?
- Did I avoid unnecessary Rule 9 ownership scenarios?
- Is any conditional future benefit being treated as already delivered?
- Are comparator source labels truthful?
