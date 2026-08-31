# Smallcaps.ai — Facts. No fluff. Product Contract v1

## Positioning

**smallcaps.ai**  
**AIM company news. Facts. No fluff.**

Smallcaps.ai is a fast, factual AIM company-news product. It surfaces the news that matters, extracts all decision-useful disclosed facts, shows only supported changes versus prior company disclosure, and records the market reaction.

The product is not an RNS summariser and must not read like a chatbot or broker research report.

## Product rule

> **Surface = shorthand. Detail = forensic.**

The default feed must be quick to scan. Clicking an item reveals the complete material factual record and the evidence behind any change statement.

## Default information hierarchy

1. **Key News** — material company news only.
2. **All News** — the full analysed AIM feed.
3. **Watchlist** — the same feed filtered to followed companies.
4. **Companies** — running factual history by company.

`Key News` is the default view.

## Key News rule

Materiality is a 1–5 score and is independent of direction.

- `1` — routine
- `2` — minor
- `3` — material
- `4` — high
- `5` — critical

**Key News = materiality 3–5.**

Scores 1–2 remain available in All News but are hidden from the default Key News list.

The amount of screen space should broadly follow information value: routine items may be one or two lines; material items may use more space when needed.

## Direction / sentiment

Direction answers **good, mixed, bad or neutral?** It must not encode materiality.

- `green` → **Positive / Good**
- `amber` → **Mixed / Watch**
- `red` → **Negative / Bad**
- `grey` → **Neutral / Routine**

Public UI uses the direction colour only for:

- one small status marker/pill; and
- a subtle 2–3px left-edge accent.

Do not tint whole cards or use coloured materiality circles.

## Materiality display

Materiality is always shown with five neutral circles:

- `1` → `●○○○○`
- `2` → `●●○○○`
- `3` → `●●●○○`
- `4` → `●●●●○`
- `5` → `●●●●●`

The circles are monochrome/neutral. Direction colour and materiality must remain visually independent.

## Public terminology

Prefer product language over source-system language:

- `Company News`, not `RNS feed`
- `News Type`, not `RNS Type`
- `Source`, not `View RNS`
- `Pre-announcement`, not `Pre-RNS`
- `Day reaction`, not `RNS reaction`
- `Material Facts`
- `What Changed`
- `Current Baseline` when history is not established

`RNS` may remain in internal ingestion/database fields where technically correct.

## Feed item contract

The compact feed surface contains only:

1. ticker + company
2. publication time / age
3. neutral materiality circles
4. direction label
5. news type
6. concise headline
7. concise take
8. pre-announcement price and same-day reaction when available
9. source link on expansion/detail

Example:

```text
SPR   ●●●●○   Positive   Disposal             07:00
Land sale brings in £12m cash
£12m sale. More cash in, balance sheet improves. Guidance unchanged.
PRE 96.5p · DAY +4.7%
```

## Writing contract — investor shorthand

The surface copy should read like a knowledgeable small-cap investor sending a concise note to another knowledgeable investor.

- short declarative sentences;
- fragments are allowed;
- finance shorthand is encouraged where unambiguous;
- assume the reader understands investing;
- lead with the important point;
- no introduction and no conclusion paragraph;
- no repetition between headline and take;
- `take` target: **20–40 words**, hard maximum **45 words**;
- no Buy/Sell/Hold, price target or fair value;
- no management-marketing language unless quoted as evidence;
- no filler such as `overall`, `it is worth noting`, `this suggests`, `investors may`, `positions the company well`, `significant milestone`, `looking ahead`, or `on balance`.

For routine news, the correct take may be extremely short:

`Routine remuneration update. No change to the investment case.`

Do not manufacture analysis where none exists.

## Detail contract

Clicking a feed item reveals:

### Material Facts

All decision-useful facts explicitly disclosed in the announcement. This section is exhaustive within the materiality of the announcement, not a selective summary.

Facts may include, where relevant:

- revenue, profit, EBITDA, margins and guidance;
- cash, debt, liquidity, covenants and funding runway;
- contract values, committed/optional elements, duration and timing;
- acquisition/disposal consideration and conditions;
- placing size, price, discount, dilution and use of proceeds;
- operational KPIs and production metrics;
- customer/order-book data;
- dates, deadlines and conditions;
- director/PDMR dealing amounts and prices;
- remuneration awards and disclosed performance conditions;
- management outlook wording where decision-useful;
- important information explicitly not disclosed when its absence affects interpretation.

Every fact must retain source provenance internally.

### What Changed

Show only changes supported by a reliable prior company disclosure or safe deterministic calculation.

Examples:

- `Net debt ↓ £24.0m → £18.2m`
- `Guidance → maintained`
- `EBITDA guidance ↓ £9–10m → c.£6m`

Never infer direction from incomplete history.

### Current Baseline

When the system lacks a reliable comparator, do **not** show unsupported arrows or directional language. Show the current disclosed position and state that the baseline is building.

Example:

```text
CURRENT BASELINE
Net debt     £14.2m
Order book   £62.0m
Guidance     In line

First company baseline in Smallcaps.ai.
```

Distinguish `history not yet in Smallcaps.ai` from `company did not disclose a comparator`.

### Price

MVP market context:

- unaffected/pre-announcement price;
- same-session/day reaction when available.

Example: `PRE 96.5p · DAY +4.7%`

Longer 5/10/20-session event studies are explicitly deferred.

### Source

Always provide the original source announcement.

## Evidence policy

Public analytical statements may be only:

- **REPORTED** — explicitly disclosed;
- **CALCULATED** — arithmetic using disclosed inputs;
- **COMPARED** — direct comparison with a valid prior disclosure;
- **DERIVED** — a tightly bounded implication directly supported by the above evidence.

Unsupported **INFERRED** or **SPECULATIVE** claims are not publishable.

If evidence is insufficient, use `Not disclosed`, `Cannot determine from this announcement`, or omit the unsupported claim.

> **Evidence first. Calculation second. Interpretation third. Never unsupported inference.**

## Visual contract

- light/off-white page background;
- white content surfaces where a surface is needed;
- dark navy/black primary type;
- restrained blue brand accent;
- green/amber/red only for direction;
- neutral grey materiality circles;
- thin borders and separators;
- subtle left-edge direction accent;
- compact spacing;
- small pills only where useful;
- no gradients, glow, giant hero, oversized cards or decorative AI motifs;
- list-first layout, not dashboard-card-first layout.

## North Star

> **Maximum signal per pixel.**

Every visible element must help the investor answer at least one of:

1. What happened?
2. What changed?
3. How much does it matter?
4. Was it good, mixed, bad or neutral?
5. What did the market do?
6. Can I verify it?

If an element does none of these, remove it.
