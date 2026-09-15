# Pass 4 — source-scoped follow-up questions

## Product and source boundary

After a successful evidence-checked card, one composer appears: **Ask about this announcement…**.
The Pass 2B card assets and existing landing styles are unchanged. The complete paste
and server-owned analysis provide context; earlier AI answers and user claims are not
new company evidence. No browsing, company memory, prices or database writes are added.

`PasteJobs.context(owner, analysis_id)` returns a defensive private snapshot only for
the owner of a complete analysis. The public analysis response does not contain raw
source text. The client supplies only question text, random request_id and turn_index;
it cannot replace the source, analysis, system prompt or conversation history.

Private-beta routes, using the existing signed session and authentication:

- GET/POST `/api/v1/analyse/{analysis_id}/questions`
- GET `/api/v1/analyse/{analysis_id}/questions/{question_id}`

POST requires JSON and `X-Smallcaps-Action: ask`, plus a matching Origin when supplied.
Results are no-store, with no CORS. Cross-owner, unknown and expired IDs disclose no
question, answer or source. Logout removes beta and paste cookies. A new pasted RNS
resets the active UI context; late responses cannot change the new conversation.

## Evidence and arithmetic

One structured FollowupAnswer request uses the configured OPENAI_MODEL. Source and
interpretation paragraphs need quotations or references to server-held facts. Checks
reject missing/fabricated quotes, wrong source IDs, unsupported numbers, changed bounds
and targeted expected/proposed/conditional/balance-date errors. Expandable source
passages are matched to original document spans. Up to two new source-backed two-operand
calculations use the existing Decimal helpers; their inputs and method stay visible.

These checks are NOT exhaustive semantic verification. A matching quote does not prove
relevance, authenticity, completeness, accounting comparability or correct negation.
General explanations, disclosure gaps and prompt injection need live/human testing.
No unsourced valuation multiple, live quote or personal investment recommendation is
requested by the prompt. Failed drafts are not displayed. No repair request is made.

## Runtime and cost bounds

- Maximum 8 accepted question attempts per analysis, including failures. One model
  request per question; 3,500 output tokens maximum; 90-second SDK timeout; retries off.
- Two active QA workers, no waiting paid queue, one active question per announcement.
  Parent analyses retain their separate two-worker pool.
- Defaults: 12 starts per owner per rolling 10 minutes and 60 globally per hour.
  PASTE_MAX_QUESTIONS_PER_SESSION is clamped to 20; PASTE_MAX_QUESTIONS_PER_HOUR to 100.
  PASTE_CHAT_ENABLED=false disables follow-ups. No model is instantiated on page load.
- Request IDs bind the exact question and turn. Replay does not spend again; altered
  IDs/payloads and stale turns are rejected. Recovery reads history first. No automatic
  paid POST retry. A user may explicitly resubmit the same idempotent request.
- Questions: 2,000 characters; encoded context: 240,000 characters. Excess context fails
  before a model call, without silently truncating the source.
- Parent TTL: 30 minutes from analysis completion, not extended by questions. Expired
  content cannot be read; janitors clear records within a further minute. An in-flight
  request may hold a snapshot until it finishes, but cannot revive an expired answer.
- Single-process/single-replica private beta only. Restart loses text and conversations.
  Graceful shutdown closes instantiated QA workers before parent workers and clears data.

The per-document request ceiling is two initial calls plus eight follow-ups, not a price
guarantee. Input tokens vary. Provider-side budgets and separate ingestion schedules are
operator-controlled; this branch makes no Railway, quota or cron change.

## Tests and release gates

`tests/test_paste_chat.py`: evidence/quantity corruption, calculations, private source
context, owner isolation, expiry, replay/conflicts/caps, auth/origin gates, sanitised
failures, SDK strict schema conversion, one-call configuration and no-model preflight.

`jobs/check_paste_conversation.py`: actual auth/API/frontend routes on isolated localhost,
injected model stubs, Chromium at 1440/768/390/320px. Includes multi-turn flow, source
passages, source switching mid-answer, lost POST recovery, literal hostile markup,
input preservation, logout and cross-browser isolation. This is not a production test
mode. Existing actual-web-app and card browser workflows remain enabled.

Local browser navigation is blocked by the container's Chromium policy; no attempt is
made to disable it. Served-browser acceptance runs in GitHub CI. Local API/evidence tests
remain executable; SDK-specific tests run in CI with pinned dependencies.

Before deployment: live full-announcement and follow-up testing with a funded, capped
key and explicit model; human review of accuracy, omissions, writing, source relevance,
false-positive rate, latency and tokens; staged HTTPS/session/proxy/single-worker checks;
explicit merge and cutover/rollback approval. The historical beta entrance remains
unchanged and should be reviewed before launch. Pausing separate market ingestion is a
separate explicit operational step. CI and screenshots do not approve public launch.

Preflight makes no model request:

```sh
python -m jobs.check_paste_conversation_live --output /tmp/chat-preflight.json
# Only in an explicitly configured test environment:
python -m jobs.check_paste_conversation_live --live --model "$OPENAI_MODEL" \
  --source /path/to/full-announcement.txt \
  --question "What conditions apply to the expected revenue?" \
  --output /tmp/chat-live-review.json
```

Live mode handles one document, at most three total requests, no retries, and stops at
first failure. It does not deploy. It always requires human review and never sets
launch_approved=true. Fixture excerpts are not substitutes for complete announcements.
No live paid-model request was made during implementation.
