# Timing, Session And Diagnostic Corrections

## Implementation

- Prior-day high/low use a one-day offset with `barmerge.lookahead_on`, so the
  completed previous day is available from the next daily interval's start on
  historical and realtime bars. No unoffset future daily high/low is requested.
- Session ranges aggregate completed one-minute bars in New York time, not the
  entire parent chart candle. Windows are half-open: Asia 18:00-00:00, London
  02:00-05:00, NY AM 08:30-11:30, NY PM 13:30-16:00. DST is timezone-derived.
- Only an observed complete, contiguous session can become a session pool.
  Partial startup sessions and sessions with missing minutes cannot publish one.
- Sweeps use the completed-session pool captured before the chart bar starts.
  A session that finishes inside a 4h candle is available to the following
  candle, never retroactively to the current candle's earlier wick.
- Confirmed candidates require full minute coverage through the exact chart
  close. Missing intrabars block candidates. TradingView's finite intrabar
  history means older bars may no longer produce candidates; old/new historical
  counts are not directly comparable. Market-data corrections remain possible.
- Session label means the latest observed completed minute, not the computer's
  wall-clock time or a claim that an entire 4h candle belongs to one session.
- Compact panel has separate Gate and Candle rows. The structural blocker is
  visible while the candle is open. Diagnostics show event age and READY,
  EXPIRED or ORDER BLOCK. READY is feature age/order eligibility, not approval.
- Diagnostic table is opaque; retired FVG boxes stop extending and turn gray,
  with MITIGATED, INVALIDATED, EXPIRED or SUPERSEDED text. Debug drawings remain
  optional/off by default. They are not executable orders or backend decisions.
- Natural payloads include `detector_revision=timing_sessions_v2`, one-minute
  coverage and timing metadata. Backend independently checks declared coverage,
  exact close and pool-before-bar ordering. It does not independently download
  market data. Older strict_v1 saved alerts remain compatible pending approval
  of their replacement, and therefore still use their old session calculations.

Score minimum 75, confirmation age 6, RVOL thresholds 0.7/1.5, consolidation
rules, ES/NQ pairing, stop buffers and RR policy are unchanged. No threshold was
relaxed to increase activity. Test alerts remain disabled.

## Regression Probe

`backend/scripts/pine_session_probe.py` emits a no-alert Pine harness using the
actual production helpers extracted from the indicator, not a Python rewrite.
It runs synthetic minute arrays against session boundaries, summer/winter/DST
transitions, midnight rollover, out-of-session extreme prices, same-bar pool
lookahead, missing minutes, partial startup and unfinished-minute confirmation.

All 12 checks passed when executed on TradingView on November 9. The compile
tool saved the temporary probe as revision 16 automatically; the full corrected
detector was immediately restored as revision 17. The probe is not the final
indicator and never emitted alerts. The existing server-side alert retains its
separate revision-15 snapshot and was not modified.

Local suite after implementation: 165 passed, zero failures, one pre-existing
Starlette/httpx deprecation warning. The tests include source contracts, probe
generation, strict webhook preflight and automated-news fail-closed behavior.
Pine compilation: zero errors and warnings. Deployment and final chart matrix
results are recorded separately after verification.

## Alert Change Requires Approval

Proposed replacement configuration, not yet applied:

- Name: `SMC LLM Candidate Detector webhook`
- Symbol/feed: `CME_MINI_DL:NQ1!` (current account's delayed NQ continuous feed)
- Timeframe: `240` (4h)
- Condition: `SMC LLM Candidate Detector -> Any alert() function call`
- Script snapshot: corrected detector, revision 17, `timing_sessions_v2`
- Inputs: score 75; age limit 6; JSON alerts true; test webhook false; Compact;
  zones/proof markers false; candidate labels true; all other existing defaults.
- Message: script-generated `alert()` JSON; no pasted static payload.
- Webhook: `https://<existing-render-host>/webhooks/tradingview?secret=<existing-secret>`
- Expiry: January 7, 2027 at 18:00 UTC, preserving the approved minute.
- Keep exactly one active matching alert. Replace ID `6022530375` only after
  user approval; verify the replacement's server-side revision and input snapshot.

No trades, broker connections, replay or automatic orders are part of this work.
