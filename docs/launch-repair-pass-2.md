# Launch Repair — Pass 2

Pass 2 brings **The AIM Daily** into the same visual system as Company News and Company Intelligence without changing its editorial or data contracts.

## North star

The Daily should feel like the editorial front page of the Smallcaps.ai product, not a separate publication or a themed microsite.

That means:

- one light product shell across News, Watchlist, Company Intelligence and The AIM Daily;
- one white header, one 1120px content grid, one blue accent and one typography system;
- editorial hierarchy through scale, whitespace and story placement rather than a dark theme, oversized display type or decorative rules;
- evidence, signal and source links remain visually explicit;
- the newsroom decides what matters; the interface does not manufacture urgency.

## Visual changes

- The Daily now loads the shared `news.css` design foundation.
- The header is structurally identical to the rest of the product.
- The page background, text, borders, blue accent and semantic signal colours use the shared light tokens.
- The masthead is restrained to the product content width.
- The edition selector is a compact segmented control rather than a terminal-style strip.
- Lead, secondary, quick-take and suppressed-story sections use clear white surfaces with subtle borders and consistent radii.
- Mobile story layouts collapse to one column and edition controls retain at least a 48px target.
- Focus, reduced-motion, print and horizontal-overflow behaviour remain explicit.

## Deliberately unchanged

- No AI prompt, model, routing, database, ingestion or Railway topology change.
- No newsroom ranking, copy-desk, publication-safety or latest-populated-edition logic change.
- All existing DOM IDs and the `aim-daily-newsroom-v1` JavaScript contract remain intact.
