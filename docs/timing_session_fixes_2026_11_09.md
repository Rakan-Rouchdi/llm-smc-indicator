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
- `behind_chart=false` keeps the table above candles on newly added instances.
  Existing instances may require Visual order -> Bring to front or re-adding,
  per [TradingView's declaration rules](https://www.tradingview.com/pine-script-docs/language/declaration-statements/).
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
detector was immediately restored as revision 17. Revision 18 adds the drawing
order correction only. The probe is not the final
indicator and never emitted alerts. The existing server-side alert retains its
separate revision-15 snapshot and was not modified.

Local suite after implementation: 167 passed, zero failures, one pre-existing
Starlette/httpx deprecation warning. The tests include source contracts, probe
generation, strict webhook preflight and automated-news fail-closed behavior.
Pine revision 18 compilation: zero errors and warnings.

## Live Chart Matrix

November 9, 2026, during the US session, on the account's delayed CME feed:

| Symbol | 5m | 15m | 1h | 4h |
| --- | --- | --- | --- | --- |
| ES | PASS | PASS | PASS | PASS |
| NQ | PASS | PASS | PASS | PASS |

PASS here means the corrected session/daily values and diagnostics rendered,
not profitable signals or an exhaustive backtest. Revision 17 supplied the
matrix; revision 18 changes drawing order only and compiled cleanly. The NQ
5m/15m indicator initially needed extra calculation time after the chart switch;
both were read again after their tables populated, not counted as empty passes.

All eight panels showed identical completed London-session levels per symbol.
Independent aggregation of all 36 five-minute bars from 07:00 through 09:55 UTC
matched exactly: ES low/high 7385.75/7434.75; NQ 26751.25/27147.25. Daily candles
independently matched previous-day low/high: ES 7322.25/7469; NQ 26366.5/27425.
This catches the old higher-timeframe session contamination and delayed daily
level update. NY_AM labels and OPEN/PREVIEW states agreed with observed data.

Tables, labels, boxes and lines were inspected for all eight combinations.
Debug zones returned 30 retained zones per chart; retired zones were gray and
stopped extending. Candidate labels were present on ES 5m and NQ 5m/15m, absent
on the other inspected histories. No Pine line objects were returned, as expected:
the current clean version uses optional labels/boxes, not `line.new` BOS trails.
No candidate was active during the sampled current bars; thresholds were not
weakened to manufacture a signal. Historical counts depend on available minute
history and are not a win-rate measurement.

XAUUSD 15m correctly showed Unsupported chart, Companion BLOCK and Candidate
NONE. It is a negative safety/UI test, not validation of gold trading support.

Screenshots remain in
`/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/`:

- `timing_sessions_20261109_{ES,NQ}_{5,15,60,240}.png` (eight matrix captures)
- `timing_sessions_20261109_probe_pass.png` (12 runtime assertions)
- `timing_sessions_20261109_XAUUSD_unsupported.png`

The matrix screenshots exposed candles painting over the diagnostic panel,
leading to revision 18. The Mac then locked, preventing the final native visual
order check and closing the Pine editor. The last compact capture contains the
open editor and is not evidence of a clean final layout. A final screenshot
after unlocking remains required; do not claim that last visual check passed.

## Hosted Deployment

PR #5 merged as `8500edc`. Timing/backend changes are in `ca6747a`; explicit news
deployment settings in `0808a6f`; drawing order in `4fe5169`; safe publisher HTTP
diagnostics in `bc77980`. No secret or `.env` file was committed.

Render's service already followed `main`, but its Blueprint still followed
`codex/phase6c-render-neon`. The Blueprint was corrected to `main`; its reviewed
sync changed NEWS_PROVIDER and added refresh interval/timeout. Database,
dashboard, webhook and OpenAI credentials were neither changed nor printed.

Effective configuration: `NEWS_PROVIDER=forexfactory`,
`REQUIRE_VERIFIED_NEWS=true`, `NEWS_MAX_AGE_HOURS=24`,
`NEWS_REFRESH_INTERVAL_MINUTES=60`, `NEWS_FETCH_TIMEOUT_SECONDS=10`.

The first production refresh at 16:21:41 UTC failed with `HTTPStatusError`.
The publisher worked locally earlier (37 USD events, 23 elevated HIGH,
publication 15:42:15 UTC), but that does not prove reachability from Render.
The original error did not retain its status, so its exact cause is unknown;
do not assume an IP ban or rate limit. Subsequent failures retain a safe numeric
HTTP status. No alternate proxy, weakened freshness policy or retry loop was
introduced. Durable hourly cooldown survives restarts.

Observed deployed result: database OK, decision worker running, zero failed
jobs, news ES UNKNOWN/NQ UNKNOWN, readiness false, refresh enabled but no success.
Public `/health` returns 200; unauthenticated `/dashboard` returns 401;
authenticated dashboard renders the news failure and historical-decision warning.
The latest stored BUY is the November 8 delivery test, not a new natural setup.
No test webhook or paid OpenAI call was made during this rollout.

**Automatic refresh is enabled but not yet operationally verified.** Approval
remains blocked until a valid hosted snapshot succeeds. If the publisher keeps
rejecting the Render request, use a supported/authorized calendar provider or
roll back to manual mode with genuinely fresh verified coverage; never renew old
dates or switch to mock news to make readiness green. Render Free sleep and
third-party feed completeness remain independent reliability limitations.

## Alert Change Requires Approval

Proposed replacement configuration, not yet applied:

- Name: `SMC LLM Candidate Detector webhook`
- Symbol/feed: `CME_MINI_DL:NQ1!` (current account's delayed NQ continuous feed)
- Timeframe: `240` (4h)
- Condition: `SMC LLM Candidate Detector -> Any alert() function call`
- Script snapshot: corrected detector, revision 18, `timing_sessions_v2`
- Inputs: score 75; age limit 6; JSON alerts true; test webhook false; Compact;
  zones/proof markers false; candidate labels true; all other existing defaults.
- Message: script-generated `alert()` JSON; no pasted static payload.
- Webhook: `https://<existing-render-host>/webhooks/tradingview?secret=<existing-secret>`
- Expiry: January 7, 2027 at 18:00 UTC, preserving the approved minute.
- Keep exactly one active matching alert. Replace ID `6022530375` only after
  user approval; verify the replacement's server-side revision and input snapshot.

Exact unchanged detection inputs: companion override blank (automatic ES/NQ
pairing); pivots 3/3; BOS break 2 ticks; FVG minimum 2 ticks; sweep buffer 1 tick;
equal-level tolerance 4 ticks; SMT lookback 20; RVOL length 50 and thresholds
0.70/1.50; ATR length 14; displacement 1.0 ATR; consolidation lookback 20,
range 2.0 ATR and efficiency 0.30; HTF input 60 (effective daily on 4h); HTF
EMAs 50/200; setup expiry 30 bars; minimum RR 1.50; target RR 2.0; stop buffer
2 ticks; minimum score 75; confirmation age 6. Diagnostic table true, Compact;
zones false; proof markers false; candidate labels true; JSON alerts true;
test webhook false. Evaluation/alert emission occurs on confirmed bar close.

Read-only alert listing still showed exactly one active alert, ID `6022530375`,
revision 15, NQ 240, test false, last_fired null. Its exact existing expiration
is January 7, 2027 at 18:00:21 UTC; the proposal preserves the approved 18:00
minute. Chart edits do not update that server-side snapshot. No alert was
created, deleted or modified. News fetch success and the final native visual
check should be resolved before approving replacement.

No trades, broker connections, replay or automatic orders are part of this work.
