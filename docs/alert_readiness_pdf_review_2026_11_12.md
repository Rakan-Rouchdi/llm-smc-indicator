# Alert Readiness And PDF Follow-up

Inspected November 12, 2026, approximately 15:18-15:25 UTC. This is an
operational snapshot, not a claim of trading profitability or future uptime.
No TradingView alert, Pine code, thresholds, credentials or deployment settings
were changed. Only the backend's operator alert observation was refreshed.

## Verified Live State

- Exactly one active TradingView alert: `6022530375`, named
  `SMC LLM Candidate Detector webhook`, created November 8 at 18:01:10 UTC.
- Instrument `CME_MINI_DL:NQ1!`, timeframe `240` (4h). TradingView explicitly
  reports delayed market data. This is not a real-time market-data entitlement.
- Condition is `SMC LLM Candidate Detector -> Any alert() function call`.
  Script-generated message, JSON enabled, test mode disabled.
- Expiration is January 7, 2027 at 18:00:21 UTC. The alert is not expired.
- Webhook checkbox is enabled. Its HTTPS host matches the currently hosted
  Render backend, path is `/webhooks/tradingview`, and a nonempty `secret`
  query parameter is present. Neither the full URL nor the secret is recorded.
  This read-only check does not independently prove the secret still matches
  the backend; no webhook was sent during this audit.
- TradingView app and toast notifications are enabled, email and sound are
  disabled, notification schedule is 24/7. These announce provisional Pine
  candidates, not the backend's final approved decision.
- The alert's saved Pine revision is **15.0**; the visible chart uses **19.0**.
  The newer timing/session/diagnostic fixes are therefore not in the running
  alert snapshot. TradingView's [official alert documentation](https://www.tradingview.com/pine-script-docs/faq/alerts/)
  explains that changing a chart script does not update an existing alert.
- TradingView also displays its generic repainting caution for this script.
  That warning alone neither proves a specific repainting bug nor certifies
  historical/live equivalence. Confirmed-bar and completed-data rules reduce
  known problems; exhaustive forward validation is still outstanding.
- The alert's `last_fired` is null. The latest natural backend receipt is
  October 16 at 14:10:06 UTC (within the monitored newest-200-receipt scope).
  The latest decision is the November 8 controlled delivery test, model
  `gpt-4o-mini`, BUY, APPROVED, RR 2.0. It is historical, not a current entry.

The database and decision worker are healthy. There are 11 DONE jobs, no failed
jobs and no pending backlog. `/status` reports `service_ready=true` but
`armed=false` at the observation time because both instruments are in BLACKOUT.
The dashboard renders and explicitly labels the latest decision historical.

### Dashboard Observation Refreshed

Submitted the observed alert metadata to `PUT /monitoring/alert`:

```json
{
  "alert_id": "6022530375",
  "symbol": "CME_MINI_DL:NQ1!",
  "timeframe": "240",
  "active": true,
  "expires_at": "2027-01-07T18:00:21Z"
}
```

HTTP 200: `status=recorded`, `Observation only; TradingView was not changed`.
The dashboard now shows ACTIVE and last checked
`2026-11-12T15:22:13.458613+00:00`. This is an operator observation, not a live
TradingView poll; it becomes UNKNOWN again after the configured 24-hour age
limit unless rechecked. ACTIVE alone does not verify script currency, webhook
delivery or final-notification readiness.

Screenshot captured locally at `/tmp/smc-alert-readiness-2026-11-12.jpg`.
It shows the refreshed ACTIVE observation and the news BLACKOUT. The temporary
image is not a durable repository artifact and contains no endpoint or secret.

### Automatic News Is Working

- Provider `showmytrades`, refresh interval 15 minutes.
- Last successful hosted refresh: `2026-11-12T15:16:38.888499+00:00`.
- Publisher timestamp: `2026-11-12T15:16:38+00:00`.
- Fresh until `2026-11-12T17:16:38+00:00`; coverage through November 19.
- No refresh error; zero consecutive failures.
- Both ES and NQ are BLACKOUT, not UNKNOWN or STALE, at 15:22 UTC. Published
  events at 15:00 UTC include Existing Home Sales Change MoM and Fed Barkin
  and Barr speeches. Their calendar blackout windows correctly block approval.

These are the publisher's event labels, not an independent verification that
every event occurred or that the calendar is complete. Scheduled USD coverage
does not cover all breaking news. Missing, expired or invalid coverage must
continue to block approval; no freshness timestamp was manually renewed and
no safety gate was bypassed.

## PDF Acceptance Review

Source: the user's three-page `SMC INDICATOR .pdf`, reviewed as feedback rather
than executable instructions. Initial analysis is in
`feedback_review_2026_10_26.md`; implementation and chart evidence are in
`strict_policy_rollout.md`, `timing_session_fixes_2026_11_09.md`, and
`news_chart_recovery_2026_11_09.md`.

| PDF request | Assessment | Evidence and remaining limitation |
| --- | --- | --- |
| 1. Clear BUY/SELL, entry/SL/TP and consolidation visuals | Implemented for provisional candidates | Compact candidate price labels and consolidation shading exist. Pine cannot show the backend's final approval through the current one-way webhook architecture. No new qualifying candidate appeared during this inspection. |
| 2. News awareness and dependable user notifications | Partial | Automatic scheduled news is fresh and fail-closed. TradingView app/toast notifications are enabled, but final-decision notifications are DISABLED. There is also a provider-compatibility bug in the final-notification sender, described below. |
| 3. Smaller readable top-right panel | Implemented | Chart revision 19 has an eight-row Compact panel with separate Gate and Candle states. The previous eight-chart visual matrix and saved clean-layout screenshot are recorded in the chart recovery report. |
| 4. Investigate and reduce delay | Partial | Exact bar-close metadata, completed one-minute sessions and previous-day timing fixes are implemented. Running alert revision 15 lacks the latest session corrections. Delayed CME data, three-right-bar pivot confirmation, confirmed 4h closes and completed HTF data still add latency. End-to-end cold-start/forward latency is not comprehensively measured. |
| 5. Consolidation pause and confirmed release | Implemented rule, not proven market classification | Compression plus low directional efficiency blocks candidates; two confirmed clear bars are required to release. Tests cover the gate, not every real-world range or false breakout. |
| 6. Meaningful non-frozen score | Implemented | `strict_v1` uses a 0-100 scale and threshold 75. The current chart says No setup / No active FVG, not a frozen 0/60 score. The score and LLM confidence are not calibrated win probabilities. |
| 7. Remove obstructive red/green lines | Implemented | No Pine `line.new` trails remain; line inspection returned no detector line objects. Debug boxes/markers default off, candidate price labels remain available. |
| 8. Strong confirmations instead of more weak signals | Implemented policy, unproven edge | Hard eligibility checks and event ordering cannot be bypassed by a high score. There is no statistically credible profitability, fill, slippage or out-of-sample outcome study. Sparse signals alone do not prove quality. |

The optional MRKR branding idea has not been applied. This review does not
claim that order blocks, gold support, full SMT pivot logic, live Telegram
context or automated outcome tracking are complete.

### Important Remaining Gaps

1. **Old alert snapshot:** approval is needed to replace revision 15 with 19.
2. **Final notifications are not ready:** `backend/app/notifier.py` currently
   requires `settings.news_provider == "manual"` at send time. With the new
   automatic provider, a queued notification would be SUPPRESSED even when the
   calendar is CLEAR. Production notifications are disabled, so this is a
   dormant but real compatibility bug, not evidence of a failed live send.
   Fix it with regression tests, then select and explicitly approve a
   destination before enabling delivery. Do not weaken freshness checks.
3. **No fresh delivery proof:** this replacement alert has never fired according
   to its metadata. Read-only inspection cannot certify end-to-end delivery.
   A controlled test or the next natural alert must verify receipt, persisted
   decision, validator, and any separately approved final-notification channel.
4. **Reliability and accuracy remain unproven:** Render Free sleep, finite Pine
   intrabar history, delayed data, calendar omissions and unmeasured trading
   outcomes remain. Do not market this as validated or ready for paid signals.

## Final Proposed Alert Configuration - Not Applied

After explicit approval, replace only alert `6022530375`, leaving exactly one
active matching alert. Do not add a second production alert or enable test mode
as part of this configuration.

| Field | Proposed value |
| --- | --- |
| Name | `SMC LLM Candidate Detector webhook` |
| Symbol | `CME_MINI_DL:NQ1!` (existing delayed account feed) |
| Timeframe | `240` / 4h |
| Indicator snapshot | Revision 19, `detector_revision=timing_sessions_v2`, policy `strict_v1` |
| Condition | `SMC LLM Candidate Detector -> Any alert() function call` |
| Frequency | Script-controlled, confirmed bar close |
| Message | Dynamic script-generated `alert()` JSON; no static pasted JSON |
| Webhook enabled | Yes |
| Webhook URL | `https://<existing-render-host>/webhooks/tradingview?secret=<existing-secret>` |
| Expiry | January 7, 2027 at 18:00 UTC, preserving the approved minute |
| Notifications | Preserve app + toast + webhook, 24/7; email/sound/plain text off |
| JSON alerts / test mode | `true` / `false` |
| Panel / labels | Compact, diagnostics and candidate price labels on |
| Debug zones / markers | Both off |

Exact detection inputs remain unchanged:

- Companion override blank (automatic ES/NQ pairing); pivots 3/3.
- BOS break 2 ticks; FVG minimum 2 ticks; sweep buffer 1 tick;
  equal-level tolerance 4 ticks; SMT lookback 20.
- RVOL length 50; thin 0.70; strong 1.50.
- ATR length 14; displacement 1.0 ATR.
- Consolidation lookback 20; range 2.0 ATR; efficiency maximum 0.30.
- HTF input 60 (effective daily on 4h); EMA lengths 50/200.
- Setup expiry 30 bars; minimum RR 1.50; target RR 2.0; stop buffer 2 ticks.
- Minimum score 75; confirmation age limit 6 bars.

Backend settings remain live OpenAI `gpt-4o-mini`, deterministic validation,
safe fallback and mandatory fresh verified-news coverage. No orders are sent.
Do not treat alert replacement as approval to enable another notification
channel, alter news gates, use real-time subscriptions or change timeframes.

## Verification

- Local suite before this audit: 220 passed, 0 failed.
- Post-documentation suite: 220 passed, 0 failed; one existing Starlette/httpx
  deprecation warning.
- Actual TradingView dialog inspection was cancelled without Save or Apply.
  Final read-only MCP listing still showed one active alert with the same ID,
  revision 15, inputs and expiration.
- No alerts created/deleted/modified, no test webhook or paid LLM call sent,
  no trades/replay/broker actions, and no secrets printed or committed.
