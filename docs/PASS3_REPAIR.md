# Pass 3 repair and acceptance

Work resumed on 16 September 2026 from b939f9b.

The production request at 08:17:54 UTC had 77,609 characters, 6,529 input tokens,
393 output tokens, and failed CARD_EVIDENCE / UNSUPPORTED_NUMBER in 6.87 seconds.
This is not a provider timeout. The screenshot cannot establish which field failed.

Re-fetch the committed, hash-checked public corpus for local reproduction (zero AI
calls). Preserve previous failed evaluations. Fix table units, periods and evidence
scope with positive and negative regression controls. Keep the UI, one-request
budget, small-model baseline and private temporary sessions. No source logging for
ordinary user requests, no automatic model escalation or blind repair retries.

Acceptance requires full-document model evaluation, source review and deployed
browser tests, not merely green unit tests. The exact browser paste is not stored;
test the full issuer release and explicit formatting variants without calling them
byte-identical to the user's paste. Report observed latency, all attempt costs,
remaining limitations and deployment status honestly.
