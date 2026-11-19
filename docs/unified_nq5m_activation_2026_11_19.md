# Unified NQ 5m Activation

User-approved migration on November 19, 2026. No trades, broker connection,
replay, weakened news gates or synthetic production approval were used.

## Saved Configuration

Both existing alerts were edited in place, preserving IDs and history. No new
alert was created and none was deleted. The old saved script snapshots were
replaced, not left running alongside the new ones.

| Setting | Candidate | Outcome prices |
| --- | --- | --- |
| Alert ID | 6067103295 | 6067783354 |
| Name | SMC LLM Candidate Detector webhook | SMC LLM Outcome Prices NQ |
| Indicator | SMC LLM Candidate Detector revision 24 | Same script, revision 24 |
| Symbol / interval | CME_MINI_DL:NQ1! / 5m | Same |
| Chart | Standard candles, extended session, unadjusted | Same |
| Condition | Any alert() function call | Same |
| Alert stream | SMC setups | Outcome prices |
| JSON / test | Enabled / disabled | Enabled / disabled |
| Rule score / confirmation age | 75 / 6 bars | Unused for price output |
| Feed ID | Unused in setup mode | nq-paper-v1 |
| Message | Script-generated setup JSON | Script-generated bounded 1m-bar batches |
| Delivery | Existing app + toast + webhook | Webhook only |
| Expiry (UTC) | 2027-01-07 18:00:14 | 2027-01-07 18:00:41 |
| Path | /webhooks/tradingview | /webhooks/tradingview/prices |

Both destinations privately matched the existing production HTTPS host and
Render WEBHOOK_SECRET. No destination or secret value is recorded here.
All detector thresholds are unchanged from the
[approved configuration](unified_indicator_audit_2026_11_17.md).

Candidate snapshot was saved at approximately 16:23 UTC, price snapshot at
16:25:59 UTC. The visible chart was restored to **SMC setups / Compact** with
candidate price labels on, zones/proof markers off, JSON on and test off.
Only the main custom indicator plus built-in Volume remain on the chart.
[Saved clean layout and both active jobs](screenshots/smc_unified_nq5m_active_20261119.png).
TradingView briefly displayed Activating for the price job after it had already
delivered; refreshing the saved layout showed both jobs Active, matching MCP.

## Backend and Safety

- Protected production dashboard and forward-testing page loaded successfully.
- Database OK, worker running, zero failed jobs, no pending backlog.
- OpenAI / gpt-4o-mini configured; safe fallback and deterministic validation
  unchanged. No OpenAI credential was revealed or edited.
- REQUIRE_VERIFIED_NEWS=true; automatic ShowMyTrades refresh remains enabled.
- ES/NQ coverage CLEAR; last successful refresh 16:22:20.561435 UTC, source
  published 16:20:49 UTC, zero consecutive failures at that observation.
- Candidate operator observation updated at 16:26:22.038786 UTC: ACTIVE, NQ 5m.
  Dashboard reports Armed (operator-verified), not a continuous TradingView poll.
- Private final-decision notifications remain configured. Price batches do not
  call the LLM or send BUY/SELL notifications.

## Delivery and Outcome Boundaries

Real unified price delivery was confirmed:

- TradingView log: **SMC LLM Outcome Prices NQ**, emitted at **16:30:00 UTC**,
  **Webhook successfully delivered**.
- Payload: tradingview_price_feed / paper_ohlcv_v1 / nq-paper-v1,
  CME_MINI_DL:NQ1!, standard_unadjusted, contract NQZ2026.
- Backend last_received: **16:30:00.986441 UTC**, approximately 986 ms after the
  second-resolution emission timestamp; this is not HTTP response latency.
- Latest stored minute bar advanced from 16:15 to **16:20 UTC**;
  outcome_tracking=RECEIVING. The ten-minute market-data delay remains visible.
- Refreshed authenticated Forward testing page displayed RECEIVING and the
  same 16:20 UTC stored-bar timestamp.
- Backend remained armed with CLEAR coverage and no new candidate receipt.
- [Chart and successful delivery proof](screenshots/smc_unified_delivery_20261119.png).

The pre-migration 16:25 legacy delivery is not counted as unified revision-24
delivery. Old names in historical log entries are retained history, not duplicate
active alerts.

No natural candidate fired during monitoring through approximately 16:32 UTC. The latest
decision remains the November 13 delivery test: NO_TRADE / REJECTED,
deterministic-preflight, with blackout and consolidation reasons. It is not a
new NQ signal, OpenAI success today, or an eligible paper outcome.

The fixed cohort retains its November 13 start and existing history. Its one
receipt is an excluded DELIVERY_TEST; there are zero eligible approved setups
and no measured WIN/LOSS results. Review the new 5m window beginning November 19
at approximately 16:23 UTC separately from prior 4h observations. The hosted
"Revision 19 cohort" label describes the original protocol; Pine revision 24
preserves detector timing_sessions_v2 and policy strict_v1.

The feed is delayed. Price transport success does not prove fresh tradable
entries, predictive accuracy, a candidate-to-OpenAI-to-Telegram cycle, or profit.
Test mode remains off; no fake candidate was generated to manufacture success.

## Verification and Maintenance

- Baseline and post-change backend suites: 328 passed, zero failed each.
  One existing Starlette/httpx deprecation warning.
- Pine logic unchanged in this activation. Revision 24 previously compiled
  with zero errors and warnings and remains the saved snapshot for both jobs.
- Manual updated to handbook 1.1, rendered and visually reviewed: 16 pages.
- No backend deployment or environment change was required.
- Keep hosted TradingView alerts, Render, Neon and the existing uptime monitor
  operating. The local Mac/backend/quick tunnel is not required for this path.
- Renew both alerts before January 7, 2027. Verify and refresh the dashboard's
  operator observation periodically; it becomes UNKNOWN after 24 hours.

## Security Follow-up

An initial Render accessibility snapshot unexpectedly exposed the existing
dashboard password despite its masked presentation. The user was informed.
It was not copied into files or commits; OpenAI and Telegram tokens were not
revealed. The dashboard password should be rotated manually in Render, followed
by re-login. Do not rotate WEBHOOK_SECRET as part of that unrelated password
change, or the alerts will need another authorized destination update.
