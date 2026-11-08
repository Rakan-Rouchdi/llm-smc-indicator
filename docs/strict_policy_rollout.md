# Strict Policy and Reliability Rollout

Implemented November 8, 2026. Follows the findings in
[feedback_review_2026_10_26.md](feedback_review_2026_10_26.md).

## Delivery Status

Local backend implementation and Pine chart validation are complete. The hosted
backend has not been deployed from this branch. No TradingView alert was created,
deleted, renewed, or edited. The existing alert `5647010108` was inspected:
inactive, expired October 18 at 17:48:44 UTC, last fired October 16 at 14:10 UTC.
There is still exactly one existing alert, not one active alert.

The chart indicator was updated and saved as Pine revision 15. Inputs were
inspected: JSON alerts enabled, test mode disabled, score minimum 75,
confirmation limit 6, Compact panel, FVG zones/proof markers hidden, numeric
candidate labels enabled. The chart remains on delayed NQ 4h.

No trades, broker connection, or replay tools were used. No `.env` was edited,
printed, staged, or committed. Both `.env` and `backend/.env` remain ignored and
untracked. One initial inherited provider test selected live OpenAI from local
configuration and may have issued a request. Test isolation was fixed afterward;
subsequent tests and preview explicitly blank credentials and use mock/fake
providers. No new controlled production webhook was sent.

## What Changed

- Pine emits `diagnostics.bar_close_time` from actual `time_close` in natural and
  test payloads. `bar_time` retains its opening-time meaning. Shortened session
  bars no longer depend on a guessed nominal close.
- `strict_v1` hard gates require aligned BOS and HTF bias, an active directional
  FVG retest, recent liquidity evidence, aligned companion timestamps, sufficient
  volume, a confirmed consolidation exit, and valid risk geometry.
- Liquidity must occur on/before BOS; FVG formation must occur on BOS or within
  two bars afterward; retest must be later. All evidence is bounded to six bars
  by default. This is an age/sequence approximation, not a full market-leg model.
- Score weights sum to 100: FVG 25, BOS 20, sweep 10, SMT 10, HTF 15, strong RVOL
  10, current-bar displacement 10. Minimum is 75. Hard gates cannot be offset by
  a high score. Displacement is a bonus, not a mandatory retest condition.
- The backend recomputes the score and checks reported evidence consistency.
  It does not independently verify OHLCV truth against a second market feed.
- Consolidation still uses compression AND low efficiency; two confirmed clear
  bars are required to release the pause. No universal range-detection claim.
- Stop anchors use only eligible recent sweeps. Entry/target are rounded to the
  instrument tick. Signal close must remain between source stop and target.
- Stable setup IDs use symbol, timeframe, opening timestamp and policy version,
  not a changing historical bar index. One marker per FVG even with alerts off.
- Long BOS and entry/SL/TP lines are removed. Compact panel has seven rows;
  expanded diagnostics remain optional. Numeric labels explicitly say CANDIDATE.
  They are not filled positions or backend-approved signals.
- Known-invalid setups stop before LLM invocation. News is checked again after
  the model call. Live-provider fallback becomes held `NO_TRADE`, not a mock BUY
  presented as live approval. Existing historical decisions are not rewritten.
- Receipt timing records validation, DB connection, lookup, commit and total
  application latency. Safe request IDs and setup hashes correlate logs;
  execution metadata records provider and receipt-to-processing duration.
- Dashboard distinguishes worker/database readiness, alert observation status,
  stale decisions, news coverage and disabled/failed/ambiguous notifications.

## Database Changes

`init_db()` creates three additive tables on SQLite or PostgreSQL:

| Table | Purpose |
| --- | --- |
| `calendar_coverage` | Source, coverage window and verification time |
| `alert_observations` | One operator-recorded alert ID, expiry and check time |
| `notification_outbox` | Unique decision delivery, bounded retry and status |

Existing `news_events` is now populated by authenticated complete calendar
snapshots. Existing setup, decision and job tables keep their schema. Back up
Neon before deployment. No production database migration was executed here.

## Verified Manual Calendar

Configure `NEWS_PROVIDER=manual`, `REQUIRE_VERIFIED_NEWS=true`,
`NEWS_MAX_AGE_HOURS=24`. An operator must verify a complete calendar against a
reliable published source before submitting it. The app does not scrape or
certify that source, ingest live headlines, or infer market sentiment.

Use timezone-aware ISO timestamps (UTC recommended). Include events whose
blackout windows overlap coverage, including events just outside its boundary.
Coverage must include the verification time, span at most 31 days, and be
reverified within 24 hours by default. Missing/stale coverage is UNKNOWN and
blocks approval. An empty events list is permitted only when the operator has
actually verified that coverage is clear.

Example shape only, **not a verified calendar to upload**:

```json
{
  "source": "Verified source and date, supplied by operator",
  "coverage_start": "2026-11-09T00:00:00Z",
  "coverage_end": "2026-11-10T00:00:00Z",
  "events": [{
    "event_id": "replace-with-source-event-id",
    "title": "Replace with verified event title",
    "event_time": "2026-11-09T13:30:00Z",
    "impact": "HIGH",
    "symbols": ["ES", "NQ"],
    "blackout_minutes_before": 30,
    "blackout_minutes_after": 30
  }]
}
```

Set `MVP_BASE_URL`, `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` privately in
the terminal environment; do not put credentials in command arguments or docs.
From `backend`, submit a prepared file:

```bash
.venv/bin/python -m scripts.update_operations news-calendar /path/to/verified-calendar.json
.venv/bin/python -m scripts.check_mvp_status
```

The same credentials protect calendar reads/writes, status, raw payloads and
notification status. Remote helpers require HTTPS and do not follow redirects
with credentials. `/health` remains public process liveness only.

## Alert Observation and Renewal

After checking the actual TradingView alert, submit an observation file:

```json
{
  "alert_id": "REPLACE_WITH_ACTUAL_NUMERIC_ID",
  "symbol": "CME_MINI_DL:NQ1!",
  "timeframe": "240",
  "active": true,
  "expires_at": "REPLACE_WITH_ACTUAL_UTC_EXPIRY"
}
```

```bash
.venv/bin/python -m scripts.update_operations alert-observation /path/to/alert-observation.json
```

This does not change TradingView. Expired observations stay EXPIRED. Active
observations become UNKNOWN after 24 hours without rechecking. EXPIRING means
within seven days. The dashboard does not claim it is polling TradingView live.
No automatic expiry email, new UptimeRobot monitor, or renewal is configured.

**Proposed replacement, requiring user confirmation after deployment checks:**

| Setting | Value |
| --- | --- |
| Existing alert to replace | `5647010108`, expired; no duplicate |
| Name | `SMC LLM Candidate Detector webhook` |
| Symbol / timeframe | `CME_MINI:NQ1!` / `240` (account resolves delayed feed) |
| Source | Updated `SMC LLM Candidate Detector`, policy `strict_v1` |
| Condition | Any alert() function call |
| Message | Script-generated dynamic JSON; no pasted static JSON |
| JSON alerts / test input | Enabled / disabled |
| Score / confirmation limit | 75 / 6 bars |
| HTF input | 60; automatically escalates to daily on 4h |
| Webhook | `https://<existing-host-redacted>/webhooks/tradingview?secret=<redacted>` |
| Expiration | Longest permitted account duration; record actual expiry before confirmation |

Keep the current hosted endpoint and secret unless a separately approved
rotation is needed. Do not resume the old snapshot as a substitute for replacing
it. [TradingView snapshots code and inputs when creating an alert](https://www.tradingview.com/pine-script-docs/concepts/alerts/).

## Final Notifications

Off by default (`ENABLE_NOTIFICATIONS=false`). Configure either an HTTPS JSON
receiver in `NOTIFICATION_WEBHOOK_URL`, or `TELEGRAM_BOT_TOKEN` plus
`TELEGRAM_CHAT_ID` privately in hosting environment variables. A generic webhook
receives the application's JSON envelope; it is not a Slack/Discord-specific
adapter. Obtain approval for the destination before enabling standing delivery.

Only newly approved, fresh, non-test, non-mock BUY/SELL decisions with CLEAR
verified news are enqueued in the decision transaction. No historical backfill.
Recheck freshness, expiry, news, destination and approval before sending.
Entry status is `PENDING_HUMAN_REVIEW`, never a fill claim.

Statuses: QUEUED, PROCESSING, SENT, SUPPRESSED, FAILED, UNKNOWN. HTTP 429/5xx have
at most three attempts; other unsuccessful responses fail. Timeouts and expired
send leases are UNKNOWN and need reconciliation, not blind replay. A receiver
should honor `Idempotency-Key: smc-decision-<id>`. External delivery cannot be
guaranteed exactly once; Telegram does not provide application-level idempotency.
Changing destinations suppresses old queued messages instead of sending them
to an unexpected recipient. No live notification destination was used in QA.

## Latency and Readiness

`GET /status` requires dashboard authentication. The CLI now supports hosted
Neon via `/status`; it does not inspect an unrelated local SQLite file unless
`--database` is explicitly supplied. Exit status is nonzero when not armed.
The response keeps liveness, readiness and observed alert/news readiness separate.
Latest natural receipt searches the newest 200 stored receipts, excluding tests.

Receipt p95 is the last 500 requests in the current process and resets on restart.
It excludes edge/network transit and platform boot time. Inspect hosted logs
for `webhook_receipt` and `decision_persisted`, using setup hashes for correlation.
Do not dump URLs or headers. Do not acknowledge before the durable receipt commit.

The local sample returned 202 and stored a mock BUY/APPROVED; measured application
acknowledgement was 7.99 ms (SQLite, one warm request, not a hosted benchmark).
Local health/dashboard returned 200. This does **not** establish a fix for the
three historical TradingView timeout reports. Hosted warm, idle/cold, duplicate,
failure and concurrent-request latency measurements remain a rollout gate.
[TradingView cancels requests exceeding three seconds](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/).
[Render Free has production limitations](https://render.com/docs/free), and
[Neon can suspend idle compute](https://neon.com/docs/introduction/compute-lifecycle).
If durable cold acknowledgement cannot fit that deadline, use always-on ingress
and storage or a separate durable ingress queue. Uptime pings are not a guarantee.

## Rollout and Rollback

1. Review/merge the implementation branch, then deploy the matching backend.
2. Back up the database, verify the three new tables, keep one worker process,
   and check authenticated `/status`, `/dashboard`, and unauthenticated 401s.
3. Configure manual news and verify coverage. Keep notifications disabled.
4. Send a controlled test to the hosted webhook, confirm durable receipt, strict
   validation, safe provenance and latency. Test rejection does not mean delivery failed.
5. Confirm the exact replacement alert configuration above, then replace exactly
   one stale snapshot, record ID/expiry, and verify the next actual webhook.
6. Configure and separately test an approved notification destination. Restore
   UptimeRobot account access separately; it is not repaired by this code.
7. Collect forward outcomes with pending-entry assumptions, spread/slippage and
   realistic costs. Strictness, score and confidence are not win probabilities.

Rollback by disabling notification delivery and stopping the new alert before
reverting application/Pine revisions together. Leave additive tables intact.
Do not automatically replay historical candidates or silently renew the old alert.

## Limits

SMT remains a rolling-window approximation, not pivot-aligned SMT. Only the most
recent FVG is tracked. Six bars span different wall-clock durations by timeframe.
Session names describe bar-open context, not necessarily the emission session.
Targets are still risk multiples, not independently verified liquidity targets.
Pivots, confirmed HTF values, bar-close emission and delayed feeds all add lag.
The new thresholds are an explicit experimental policy, not a calibrated edge.
Manual news has operator error/freshness risk; Telegram context remains mock.
Pine cannot display live backend approval or fetch this calendar directly.
This is not ready to market as a proven or reliably always-on paid signal service.
