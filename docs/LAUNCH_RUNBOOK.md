# Smallcaps.ai Private-Beta Launch Runbook

This runbook is intentionally narrow. It covers the frozen MVP only.

## 1. Production configuration

Verify these Railway variables exist on the services that need them. Do not copy secret values into GitHub or screenshots.

```text
DATABASE_URL
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_DEEP_MODEL
APP_BETA_PASSWORD
APP_ADMIN_PASSWORD
PRIVATE_BETA_MODE=true
MARKET_DATA_ENABLED=true
```

The ingestion service also uses the configured batch, evidence and daily-item limits. Production records the prompt version shipped in code; an old `PROMPT_VERSION` Railway variable is ignored.

## 2. Deploy from `main`

The merge to `main` should trigger:

- Smallcaps.ai web deployment;
- AIM ingestion deployment;
- optional standalone price-worker deployment, where that service exists.

Before the service starts, Railway runs runtime validation, creates any missing schema objects, moves unsafe legacy public rows to the owner review queue and runs the production integrity audit.

The web deployment must also pass:

```text
/_stcore/health
```

## 3. Private-beta URL and custom domain

A Railway-generated domain is sufficient for the first smoke test.

For the branded launch:

1. In Railway, attach the chosen domain, preferably `app.smallcaps.ai` while the main domain remains available for a future marketing site.
2. Railway will display the exact DNS target required for verification.
3. In Hostinger DNS, create the CNAME record exactly as Railway provides it.
4. Do not invent or reuse an old Railway target.
5. Wait for Railway to verify the domain and issue HTTPS.
6. Test both the branded URL and the Railway fallback URL before inviting users.

A root-domain launch can be used instead, but `app.smallcaps.ai` keeps the product deployment separate from a future public homepage.

## 4. Desktop customer smoke test

Open a private/incognito browser window.

- The page shows the Smallcaps.ai private-beta proposition before the password field.
- An invalid code is rejected.
- The correct code opens the latest date with publishable analysis.
- The Feed is not empty merely because the current day is a weekend or bank holiday.
- Search works for a ticker and company name.
- Most Impactful and Latest ordering both work.
- A Feed item opens the Analyst Note.
- The Analyst Note opens Company Intelligence.
- The original RNS opens in a separate browser tab.
- The Company Intelligence page starts with the latest view and continues into guidance, metrics, promises and the timeline.
- Back navigation returns to the Feed.

## 5. Mobile smoke test

Test at approximately 390px width.

- Brand and page title fit without horizontal clipping.
- Search, date and filters remain usable.
- Feed card actions are readable and tappable.
- Impact magnitude and direction are visible in text.
- Key-number and guidance tables become labelled stacked records.
- Company tables can be horizontally scrolled where required.
- No raw Streamlit toolbar or developer exception appears.

## 6. Owner QA

Open:

```text
?view=admin
```

- The admin code is different from the beta code.
- Recent ingestion, price and launch-audit jobs are visible.
- Review-required analyses are hidden from public pages.
- An item can be inspected.
- Publication requires a written source-check or correction reason.
- Manual ingestion remains a recovery path, not the daily workflow.

## 7. Monday live-market smoke test

On Monday 24 August 2026, during the AIM market window:

1. Confirm a scheduled ingestion run starts.
2. Confirm the catalogue count is recorded.
3. Confirm at least one new eligible RNS is retrieved and analysed, where the market publishes one.
4. Confirm the new record shows Analyst version `aim-intelligence-analyst-3.1`.
5. Confirm the record is either publishable or visibly held for review.
6. Confirm the original RNS link works.
7. Confirm the same source ID is not analysed twice.
8. Confirm the price cycle runs independently of the AI result.
9. Confirm a market-data failure degrades price context but does not destroy RNS ingestion.

If no eligible AIM RNS is published during the observation window, the zero-new-item result is not a failure. Repeat the check at the next eligible announcement.

## 8. Invite the first users

Start with a small private-beta group. Give them only:

- the product URL;
- the beta access code;
- one sentence: “Open the latest AIM Feed, then use Analysis and Company to go deeper.”

Do not give a walkthrough first. The final usability test is whether the product explains itself.

## 9. Daily owner check

At the end of each market day:

- inspect recent worker status;
- review held analyses;
- open a sample of original RNS links;
- check that the latest Feed date is correct;
- check API and Railway usage;
- record any customer-reported blocker.

Fix only launch blockers during the first beta week. Put feature requests onto the post-launch backlog.

## 10. Rollback

Rollback is required when a release prevents the web service starting, breaks the public research path or publishes unsafe analysis.

1. In Railway, redeploy the last successful web and ingestion deployments.
2. Do not delete PostgreSQL data.
3. Keep private beta enabled.
4. Inspect the failed deployment logs and the `launch-production-audit` job entry.
5. Fix on a branch, run the full test suite and merge only after the gate is green.

The database uses versioned analyst runs, so rolling back application code must not require destructive research-data changes.
