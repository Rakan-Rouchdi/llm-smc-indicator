# Approved Live Rollout - November 8, 2026

User approved password rotation, verified news configuration and replacement of
the expired TradingView alert using the configuration documented in
[PR #4 verification](pr4_deployment_verification_2026_11_08.md). Exactly one
active project alert must remain. No trading or broker connection is authorized.

## Dashboard Password

The password was generated securely in memory and changed only in Render's
`DASHBOARD_PASSWORD` environment setting. It is not in this document or Git.
The unchanged username and new password can be retrieved privately from the
Render service's Environment page. Store them in a password manager, not chat.
No real `.env` file was edited. OpenAI credentials were not changed or revealed.

Render configuration deployment `dep-dbob9rhsrm7s73bfpfi0` succeeded on revision
`2b3e63e`. After cutover, old credentials returned HTTP 401 and new credentials
returned HTTP 200. The public health endpoint and worker remained healthy.

## Verified Calendar Snapshot

The [snapshot](operations/news_calendar_2026_11_08.json) covers scheduled US
macro/Federal Reserve events relevant to ES/NQ from November 8 at 17:00 UTC to
November 9 at 18:00 UTC. This is a manual, bounded calendar, not a live headline
feed, global calendar, earnings service or a guarantee against surprise news.
No forecast values or financial recommendations were entered.

Sources checked on November 8:

- [Federal Reserve Board November calendar](https://www.federalreserve.gov/newsevents/2026-november.htm): Bowman's November 9 discussion at 08:40 Eastern, converted to 13:40 UTC.
- [Chicago Fed event notice](https://www.chicagofed.org/publications/speeches/2026/nov-9-leadership-greater-chicago): Goolsbee's 09:00 Central appearance, converted to 15:00 UTC.
- [Richmond Fed media advisory](https://www.richmondfed.org/press_room/media_advisories/2026/20261102_barkin_greer): Barkin's 12:15 Eastern appearance, converted to 17:15 UTC.
- [New York Fed release calendar](https://www.newyorkfed.org/research/calendars/i-nov26.html): wholesale trade at 10:00 Eastern and consumer expectations at 11:00 Eastern.
- [Forex Factory November 9 calendar](https://www.forexfactory.com/calendar?day=nov9.2026): cross-check of the USD schedule. The viewed page used Pacific time; UTC conversions above use the primary sources.
- [BLS release schedule](https://www.bls.gov/schedule/2026/home.htm): no November 9 BLS release; CPI is November 10, outside this snapshot's coverage.

Fed appearances are conservatively classified HIGH by this project's manual
policy, not claimed to be official impact ratings. Their blackout windows are
30 minutes before and after: 13:10-14:10, 14:30-15:30 and 16:45-17:45 UTC on
November 9. Wholesale trade is LOW and consumer expectations MEDIUM; the current
backend blocks HIGH events only. This scope does not enumerate every low-impact
auction/statistical publication. No high-impact scheduled US macro/Fed event
identified within the coverage interval was intentionally omitted.

Production settings: `NEWS_PROVIDER=manual`, `REQUIRE_VERIFIED_NEWS=true`,
`NEWS_MAX_AGE_HOURS=24`. The server stamps the verification time on submission.
Coverage becomes UNKNOWN at its end or 24 hours after verification, whichever
comes first, and then blocks approvals. There is no automatic calendar refresh.
Do not resubmit an old snapshot merely to renew its timestamp. Verify a fresh,
complete high-impact schedule before updating it. Unexpected news is not covered.

## Rollout Verification

Calendar submission returned HTTP 200 with five stored events. Server verification
time: `2026-11-08T17:47:16.231297Z`. ES and NQ both returned CLEAR, with Bowman's
appearance as the nearest blocking event. **Refresh is required before November
9 at 17:47 UTC**, when the 24-hour freshness limit is reached, even though the
declared coverage window ends at 18:00. No automatic refresh was installed.

An isolated in-memory SQLite check exercised 24 assertions: CLEAR at verification,
BLACKOUT at the start, event time and end of each of the three HIGH events for
both symbols, and UNKNOWN after freshness/coverage expiry. It did not change
production data. Baseline backend tests: 110 passed, zero failed, one existing
dependency deprecation warning.

### Controlled HTTP Delivery Test

- Setup: `live_rollout_delivery_test_20261108T174950Z`.
- Source: local controlled HTTP request to the public webhook, NOT TradingView.
- Payload: example Pine JSON with current test timestamps and `test_mode=true`.
  Its example prices do not describe the current market.
- Authentication: current production webhook query secret, not printed.
- Acknowledgement: HTTP 202 in 1,388.9 ms (warm end-to-end client timing).
- Database: raw payload, parsed setup, enriched context, decision and validator
  result stored; job DONE in one attempt with no error.
- Provider: live `gpt-4o-mini`, no mock fallback.
- Sample decision: BUY, confidence 100, RR 2.0, validator APPROVED.
  This is a synthetic delivery test, not an actionable signal. Confidence is
  an uncalibrated model/quality score, not certainty or a win probability.
- Latest-decision endpoint and authenticated dashboard both showed the test;
  dashboard labels it DELIVERY TEST. Notifications: zero queued/sent.

Warm HTTP success is not proof of TradingView-originated delivery or reliable
Render Free/Neon cold-start latency. The UI explicitly warned that free-service
wake-up can delay requests. No paid hosting or monitoring changes were made.

### TradingView Preparation

MCP attachment was restored by launching TradingView with CDP and opening the
saved NQ 4h layout. Inspection confirmed the sole expired alert `5647010108`
uses old Pine revision 13, whereas the chart uses revision 15. The chart inputs
match the approved settings, including score 75, confirmation limit 6, JSON
enabled and test disabled.

TradingView displays its generic repainting caution for the script. The current
code uses confirmed-bar emission and previous-confirmed HTF values, but that
does not justify promising zero feed revisions or zero multi-symbol timing
differences. No Pine code was changed to suppress the warning.

CME was closed during preparation. The approved test-disabled NQ 4h configuration
cannot be forced to emit a confirmed realtime candidate while that market is
closed. No replay, synthetic price manipulation or substitute-market alert is
authorized or used. Actual TradingView receipt remains a separate verification.

### Completed Alert Replacement

- Created alert `6022530375` at `2026-11-08T18:01:10Z`.
- Name: `SMC LLM Candidate Detector webhook`.
- Condition: `SMC LLM Candidate Detector -> Any alert() function call`.
- Symbol: `CME_MINI_DL:NQ1!` (account's delayed NQ feed); interval `240` / 4h.
- Pine revision: `15.0`; score threshold 75; confirmation age limit 6.
- JSON alert input enabled; test input disabled. Script-generated message only,
  with no static JSON replacement.
- Webhook enabled. Saved destination and query secret were privately compared
  with the current hosted backend and matched exactly. Redacted format:
  `https://<production-host>/webhooks/tradingview?secret=<REDACTED>`.
- App/toast notifications enabled, 24/7 schedule; email and sound disabled.
- Expiry displayed January 7, 2027 at 18:00 UTC, as specifically approved.
  TradingView retained seconds internally: `2027-01-07T18:00:21Z`.
- Deleted only expired alert `5647010108`, after verifying its replacement.
  Final MCP list contains exactly one alert, active, with the ID above.
- Reopened the saved alert to verify its destination, condition and expiry,
  then cancelled inspection without changing it.

The authenticated operator observation endpoint recorded this state at
`2026-11-08T18:02:22.012593Z`. This is a timestamped operator check, not continuous
TradingView polling. With the default 24-hour observation freshness limit, it
must be checked again before November 9 at 18:02 UTC or the dashboard's alert
status becomes UNKNOWN. News requires attention earlier, at 17:47 UTC.

Final hosted checks: health, authenticated dashboard and status all HTTP 200;
database OK, worker RUNNING, service ready and armed, ES/NQ news CLEAR, 11 jobs
DONE, zero pending/failed jobs. The dashboard visibly shows Armed
(operator-verified), ACTIVE and the clearly labelled DELIVERY TEST decision.
Backend notification delivery remains DISABLED; TradingView app/toasts are
separate from backend decision notifications.

No natural alert fired during this closed-market observation. The replacement's
`last_fired` is null; the last natural backend receipt remains
`2026-10-16T14:10:06.570550Z`. Therefore **TradingView-to-backend delivery from the
replacement is pending**, not certified by the controlled HTTP test. Check both
TradingView's delivery log and the backend receipt/job when the next real
candidate occurs. Do not treat the synthetic BUY or its confidence as a trade.

Local verification screenshots (no credentials or public host visible):

- `/tmp/smc-rollout-alert.png`: one active TradingView alert.
- `/tmp/smc-rollout-dashboard.png`: armed dashboard and delivery-test source.

Final backend test run: 110 passed, zero failed; one pre-existing dependency
deprecation warning. No application/Pine code or real `.env` file changed.
No trades, broker connection, replay or OpenAI credential changes occurred.
Both `.env` paths remain ignored and untracked. Temporary authentication material
used for verification is removed after the checks; the new dashboard password
remains in Render, retrievable privately by the account owner.

## Operator Follow-Up

1. Retrieve the new dashboard password privately from Render's Environment page
   and keep it in a password manager. The old password is revoked.
2. Verify and upload a fresh calendar before November 9 at 17:47 UTC. Include
   the next coverage window, not just a renewed timestamp on this snapshot.
3. Inspect TradingView and refresh its operator observation daily. Replace the
   alert before January 7 at 18:00 UTC, retaining exactly one active alert.
4. Verify the next actual TradingView receipt and durable job completion. This
   remaining delivery check and free-host cold-start risk prevent a claim of
   fully proven unattended reliability.
