# Safe Linked Flow Diagnostic

Prepared and deployed November 19, 2026. The owner confirmed password rotation
and explicitly approved the deployment and one-shot test. Render recorded the
password environment deployment as Live at 18:03 UTC. The diagnostic release
`a4149ef` became Live at 18:07 UTC; public `/health` returned `{"status":"ok"}`
and the new protected diagnostic routes appeared in the deployed API interface.

The linked live test is not yet completed. The browser's cached dashboard
credentials were rejected after rotation; the owner must authenticate with the
new password before readiness checks and the one-shot alert change. The new
password was not read, printed or committed. Both existing alerts were still
active with test mode off at the pre-test check.

Deployment `dep-dbvjl360tbcc738nbpqg` was pinned to the tested commit using
Render's specific-commit workflow. Render disables Auto-Deploy in this workflow.
PR #15 contains these changes; restore ordinary main-branch deployment only
after the reviewed changes are merged. The older documentation PR #14 overlaps
with this branch and should not be merged independently without reconciliation.

Baseline suite: 328 passed. With diagnostic coverage: 361 passed, zero failed;
one existing Starlette/httpx deprecation warning. Tests include authentication,
strict input/output validation, stale/blackout news before and after the model,
provider fallback/failure, receipt age/symbol/type restrictions, deduplication,
rate limiting and ambiguous-send suppression. Unit tests use synthetic
credentials and stub providers/transports; they are not live delivery evidence.

## What This Tests

The existing Pine test input emits one schema-valid diagnostic on the next
confirmed realtime bar. Its deliberately incomplete confluences cause normal
backend preflight to store a rejected NO_TRADE without calling OpenAI. Existing
notification rules correctly suppress all test and fallback trade pushes.

The new authenticated, operator-triggered diagnostic links that stored receipt
to a live OpenAI review, strict output schema validation, deterministic
validation, and a private Telegram message labelled **SMC END-TO-END DELIVERY
TEST**. This is an integration test with an explicit operator step, not proof
that a natural candidate passed the normal automatic approval/outbox path.

The original setup/decision remains unchanged and excluded from performance.
The diagnostic always reports final_action=NO_TRADE, includes no entry/SL/TP in
Telegram, creates no production notification or outcome, and never places an
order. A model BUY or even a validator APPROVED result cannot turn this test
into a production approval.

## Gates and Persistence

- Operator HTTP Basic authentication must be configured, including in dev mode.
- Live OpenAI, private Telegram and REQUIRE_VERIFIED_NEWS=true are required.
- News provider must be a supported verified provider. Coverage must be CLEAR
  both before OpenAI and after it, before the diagnostic message.
- Only a stored, processed, rejected NO_TRADE for a test-mode NQ 5m receipt with
  the canonical Pine `_TEST_` identifier is accepted. Its receipt must be at
  most 15 minutes old; its actual bar close must satisfy the configured setup
  age limit. Future timestamps and natural setups are refused.
- Operator must first match the setup ID against TradingView's delivery log;
  the API cannot independently authenticate TradingView's identity from the
  shared webhook secret alone.
- One run per receipt and one per UTC minute. A UUID identifies each run.
- The `flow_probes` table is created by existing `init_db`/create_all startup.
  It stores linkage, model input/output, validator/news evidence and timestamps,
  separately from production decisions/outcomes.
- UNKNOWN is committed before external I/O. Repeating a test ID only reads the
  existing result; it never retries even after a timeout/crash. Reconcile an
  ambiguous Telegram send rather than creating another test to resend it.
- Provider failure/fallback/malformed output is FAILED with no Telegram send.
  Stale/blackout news is BLOCKED. Telegram acceptance is SENT; this is not proof
  of receipt on the phone.
- Secrets are loaded only through existing settings. Exceptions record type
  names, not credential-bearing URLs or error strings.

## Password Rotation First

The owner must enter and submit the new DASHBOARD_PASSWORD in Render, retain it
in a password manager and wait for the environment deployment to become Live.
Leave WEBHOOK_SECRET, OpenAI, Telegram and news settings unchanged. Do not send
the new password in chat, reveal it for automation, or commit it. Sign in to a
fresh dashboard/Swagger session after rotation. Existing cached Basic-auth
credentials may require a fresh private-browser session.

## Controlled Live Procedure (Requires Approval)

1. Deploy the tested backend change after password rotation; confirm public
   health, authenticated dashboard/status and fresh verified news.
2. Keep existing candidate ID 6067103295 and price ID 6067783354. Do not add an
   alert or modify the price job.
3. Temporarily edit only the candidate's saved revision-24 NQ 5m snapshot:
   SMC setups, JSON enabled, test enabled, same existing webhook/secret/expiry.
   Use webhook-only notifications during the test to avoid a provisional app
   message being confused with an approved signal. No Pine source/rule change.
4. Wait for one confirmed realtime bar, match the `_TEST_` setup ID in the
   TradingView log and stored receipt, and verify the normal rejected NO_TRADE.
5. Immediately restore the candidate snapshot to test=false, original app/toast
   plus webhook notifications, and the visible chart to SMC setups / Compact.
   Confirm exactly the original two jobs remain active.
6. In the authenticated API UI, POST `/diagnostics/flow-tests` with:

   ```json
   {
     "test_id": "<new-UUID>",
     "setup_id": "<exact-stored-Pine-TEST-setup-ID>",
     "tradingview_log_verified": true
   }
   ```

7. Inspect GET `/diagnostics/flow-tests/{test_id}` for model gpt-4o-mini,
   schema_valid=true, deterministic validator result and SENT. If news is not
   CLEAR, do not override it. Ask the owner to confirm the labelled phone message.
8. Record actual evidence, timings and limitations; do not claim a WIN, trade,
   natural approval or production outbox success from this diagnostic.

Private webhook/host values and credentials must be redacted from all evidence.
No purchase, broker connection, replay or automatic alert duplication is needed.

## Ten-minute Feed Delay

The inspected chart explicitly reports ten-minute delayed CME data. The
November 19 price event emitted at 16:30 UTC contained data only through 16:20,
while backend storage followed emission by roughly one second. This is upstream
market-data delay, distinct from confirmed-bar waiting, HTTP delivery and LLM
processing. Essential plan features do not include all exchange data fees.

TradingView lists free CME delayed data at ten minutes and separate real-time
exchange subscriptions. Purchasing one is an owner decision, not part of this
test. Do not substitute unrelated instruments or relabel delayed prices as live.

Sources checked November 19, 2026:
[data coverage](https://www.tradingview.com/data-coverage/),
[exchange data subscriptions](https://www.tradingview.com/support/solutions/43000471705-how-to-purchase-additional-market-data/).
