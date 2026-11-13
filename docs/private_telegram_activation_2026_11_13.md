# Private Telegram Activation

November 13, 2026, UTC. The user explicitly approved creating a bot, storing
its token and the verified private chat ID in the existing Render service,
and sending final approved BUY/SELL notifications plus one labelled test.

## Bot And Destination

- Name: SMC Private Notifications.
- Username: `@smc_private_261113_bot`.
- Created through Telegram's official `@BotFather` in the user's account.
- Group invitations disabled and confirmed through `getMe`.
- A unique pairing message in the signed-in user's bot conversation was
  matched to a private chat with matching sender/chat IDs through `getUpdates`.
  No other chat was selected. No ongoing inbound bot-message processor runs.
- Bot usernames remain discoverable. "Private" here means the fixed one-to-one
  notification destination, not an undiscoverable bot or a Secret Chat.
- Bot token and chat ID stored only in Render environment settings. Neither
  value is recorded in this document, committed, or printed in tool output.
  Temporary credential-transfer files were removed immediately after use.
- OpenAI credentials and local `.env` files were not changed or exposed.

## Backend Diagnostic

PR #8 introduced `POST /notifications/test` and
`GET /notifications/tests/{test_id}`. The separate `notification_probes` table
records test attempts without adding setup, decision or trading-outbox rows.
Tests require dashboard authentication, configured Telegram-only credentials
and the verified-news policy. They refuse non-private/mismatched chat IDs.

Only a fixed informational message can be sent. Reusing an ID never resends;
the database also allows only one new diagnostic per UTC minute. Ambiguous
delivery is UNKNOWN and requires reconciliation. HTTP logs redact Telegram
tokens. The test does not call OpenAI, change news coverage or approve a trade.

Implementation commit: `4ecf6ee`; merge commit: `59e2b78`.
Render reported code deployment success at 17:45:44 UTC.
Baseline: 255 tests passed. Expanded suite: 271 passed, 0 failed, with one
existing Starlette/httpx deprecation warning.

## Confirmed Delivery

Exactly one outbound diagnostic was executed from the hosted Render backend:

- Test ID: `24ca504e-403f-4e40-a8db-d1686deb7dac`.
- Created: `2026-11-13T17:46:31.322180+00:00`.
- HTTP result: 200, status SENT, no error, kind TRANSPORT_TEST_ONLY.
- Telegram chat visibly displayed `SMC NOTIFICATION DELIVERY TEST` at 17:46.
- Message explicitly says it is not a BUY/SELL signal and created no setup,
  approval or order. News freshness and blackout checks remain in force for
  candidates.
- Production notifications were still disabled for the diagnostic. Their
  subsequent activation is verified below; there was no fabricated candidate,
  no replay of a past decision, and no second test message.

The user explicitly confirmed receipt on their phone. This supplements API
and Telegram Web evidence; phone receipt was not inferred from SENT alone.

## Safety And Scope

`REQUIRE_VERIFIED_NEWS=true`, automatic ShowMyTrades refresh, deterministic
validation and safe mock fallback are unchanged. Final notifications still
require an approved live BUY/SELL, fresh setup, unexpired decision and CLEAR
verified news at send time. Stale, unknown, mismatched or blackout coverage,
test setups and fallback decisions cannot be sent as live final candidates.

The existing TradingView alert and Pine logic were not touched. No trades,
broker connections or replay actions were performed. Live Telegram sentiment
context remains mocked; outgoing notifications do not enable sentiment input.
No new natural TradingView setup was generated for this test.

## Operational Verification

The first attempt to edit the still-masked `ENABLE_NOTIFICATIONS` field left
the stored value at false, despite a successful deployment. This was caught
by the live `/status` check. The non-secret switch was explicitly revealed,
changed to true and saved again. Render reported the corrected deployment
successful at 17:49:44 UTC.

Verified after activation:

- Saved `ENABLE_NOTIFICATIONS=true` and `REQUIRE_VERIFIED_NEWS=true`.
- `/status`: notification delivery CONFIGURED, database OK, worker alive,
  service ready, ES/NQ CLEAR with zero calendar-refresh failures.
- Dashboard: Armed (operator-verified), notifications CONFIGURED, no pending
  or failed jobs. Latest decision remains historical NO_TRADE; the transport
  diagnostic did not replace it with a fabricated signal.
- Persisted diagnostic still reports SENT after the activation restart.
- TradingView observation remains alert `6067103295`; no alert was modified.
- Configured provider/model remain OpenAI / `gpt-4o-mini`; this diagnostic did
  not call the model. Safe fallback and deterministic validation remain active.
- The dashboard shows `0 sent` for final trading notifications. That is correct:
  transport tests have a separate audit table and are not counted as candidates.
- Final local suite: 273 passed, 0 failed; one existing deprecation warning.
  Additional logging regressions cover path-only and bare-token debug messages,
  not just full Telegram API URLs. No actual token exposure was observed.
- `.env` and `backend/.env` remain ignored/untracked and were not edited.

No natural TradingView-to-approved-BUY/SELL notification occurred during setup.
The verified result is Render-to-private-Telegram delivery, user-confirmed on
the phone, plus unit/integration coverage of approval and stale-news gates.

To disable future sends, set `ENABLE_NOTIFICATIONS=false` in Render and deploy.
Reveal only this non-secret switch before editing it, verify its saved value,
then confirm `/status` reports DISABLED. A successful deploy alone does not
prove a masked environment value was changed.
Do not change the news policy, delete audit records or resend old candidates.
Keep the Telegram chat unmuted and permit Telegram notifications on the phone
if push notifications are desired. This hosted flow does not require the Mac
to remain running.

Screenshot: `/tmp/smc-telegram-delivery-2026-11-13.jpg` (temporary local proof,
not a repository artifact; it does not show the token or private chat ID).
