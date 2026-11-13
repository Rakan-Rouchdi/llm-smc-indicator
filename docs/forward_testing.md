# Forward Testing Protocol

This is paper observation and delivery monitoring, not order execution or proof
of profitability. Keep `REQUIRE_VERIFIED_NEWS=true`, automatic calendar refresh,
deterministic validation and fallback suppression enabled. Do not loosen the
score or change the alert to manufacture activity.

Automatic OHLC paper tracking is available through the separately approved
price feed. See `automatic_paper_outcomes.md`. Automatic observations and manual
annotations are displayed separately; uncertain automatic cases remain UNKNOWN.

## Scope

- Fixed cohort start: November 13, 2026 at 17:10:12 UTC, creation of the approved
  revision-19 alert. Expected detector `timing_sessions_v2`, policy `strict_v1`.
- The existing single alert monitors NQ 4h on a delayed feed. Chart testing on
  other instruments/timeframes does not mean they have active production alerts.
- All receipts after the start are listed, including tests, legacy, blocked,
  fallback and pending records. Eligibility is a separate column; low activity
  and rejection patterns must not disappear from evaluation.
- Only current-revision, non-test, OpenAI-requested, non-fallback, approved
  BUY/SELL decisions accept paper reviews. No real orders are ever submitted.
- A webhook without `test_mode` is not independently proven to originate from
  TradingView. Match its setup ID/symbol/time to the TradingView alert log before
  checking the source-confirmation box. No new automatic TradingView polling.

## Daily Review

1. Check dashboard health, worker/backlog, calendar fetch time and coverage,
   alert observation age/expiry, and notification failures/UNKNOWN statuses.
   A healthy HTTP endpoint alone does not prove candidates are flowing.
2. Open **Forward testing** from the dashboard. Open a receipt's detail page
   for raw payload, exact features, stored news and validator result.
3. For a real approved candidate, observe prices after its decision timestamp.
   Check entry eligibility only through the recorded decision expiry. Follow an
   entered paper setup for at most 24 hours from the decision. Do not use price
   movement before the decision to claim an achievable entry or outcome.
4. Record the chart/feed source, timezone, observation window, entry-touch time,
   and TP1/SL ordering in evidence. Never describe a paper touch as a broker fill.
5. Save WIN only if entry touched and then TP1 before SL; LOSS if entry touched
   then SL before TP1. EXPIRED requires no entry touch and an elapsed known
   decision expiry. Use UNKNOWN for unresolved results, missing data, or both
   levels touched within one candle without reliable intrabar ordering.
6. Append corrections rather than replacing prior evidence. Review history is
   retained per decision, not attached indiscriminately to future re-decisions.

The API rejects future/pre-decision observation times, observation windows over
24 hours, WIN/LOSS without entry touch/source confirmation, premature/unknown
expiry, and short/missing evidence. It cannot independently verify human notes.
Observation end is the end of the data reviewed, not the time notes were entered;
reviews may be entered later. Never extend a window to obtain a favorable result.

## Delivery Evidence

- Bar close -> backend receipt includes feed/transport delay; negative time is
  flagged, not clamped into a successful measurement.
- Receipt -> processing/model/decision record timings remain available.
- New notification attempts store start/end timestamps and SENT, QUEUED, FAILED
  or UNKNOWN status. Receipt -> API acceptance is populated only after an
  accepted send. Missing historical timing stays unknown; no backfill is invented.
- API acceptance is not Telegram phone receipt or human acknowledgement.
- Suppressed/stale/blackout decisions are not sent. Ambiguous/crashed sends are
  not blindly replayed. The timing addition does not change those policies.
- Decision/attempt records precede commit; no millisecond precision or
  cold-start delivery guarantee is implied.

## Storage And Endpoints

New additive tables: `forward_reviews` and `notification_attempts`. Existing
SQLite and Neon/PostgreSQL create them through `init_db()` on startup; no
existing records/columns are dropped or rewritten.

All endpoints require existing dashboard authentication:

- `GET /dashboard/forward-testing`: paginated review ledger (25 per page).
- `GET /forward-testing?limit=100&offset=0`: JSON export, maximum 100 per page;
  advance offset until all `total_receipts` have been retrieved.
- `POST /forward-testing/decisions/{id}/reviews`: outcome, entry_status,
  observed_until (timezone-aware ISO datetime), source_verified and notes.
- `GET /forward-testing/decisions/{id}/reviews`: append-only review history.

`/evaluation` uses the latest paper review for a decision when present, otherwise
legacy manual outcome annotations. It remains a newest-500 summary, not the
complete ledger. Neither endpoint claims calibrated accuracy, win rate or P&L.

## Weekly Assessment

Review receipt counts, eligibility/exclusion reasons, pending jobs, timing,
API delivery failures, unknown outcomes and source confirmations. Keep tests
out of market-performance evidence. Sparse signals alone prove neither an edge
nor a fault. Investigate prolonged silence against actual alert logs and chart
gates; never infer end-to-end readiness from uptime monitoring alone.

Do not market this as validated paid signals until there is a sufficiently
representative, independently reviewed forward sample and realistic execution,
fees/slippage and reliability evaluation. No fixed number of observations here
automatically establishes profitability.

## Rollback

Revert application code if needed; retain additive audit tables and records.
Do not change secrets, news gates, Pine or the TradingView alert as part of
deploying or rolling back this review UI.
