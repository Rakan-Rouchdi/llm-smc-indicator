# Live Chart Audit - November 9, 2026

## Verdict

The indicator runs and several core calculations passed numerical spot checks.
It is **not fully accuracy-validated or ready for performance claims**. Chart
layout problems were corrected, but the price-level/session and diagnostic
issues below remain. No Pine source, alert definition, thresholds, credentials,
production configuration, or production data were changed in this audit.

Checks ran approximately 15:46-15:56 UTC while TradingView reported the ES/NQ
market open. Both instruments resolved to `CME_MINI_DL` delayed feeds. Prices
updated during inspection, but this was not an exchange-real-time-data test.

## Findings

1. **Previous-day levels have inconsistent historical/live availability.**
   `pine/smc_llm_candidate_detector.pine:135` requests `high[1]`/`low[1]` from
   daily bars without `lookahead=barmerge.lookahead_on`. On historical intraday
   bars, the default lookahead-off mapping delivers the requested daily value
   at the end of the daily interval; realtime availability differs. The
   previous completed daily value should be mapped consistently from the
   beginning of the next day. This is a source-level timing defect, not proof
   that it caused any particular missed alert. The daily pool is also overridden
   whenever completed-session or equal-pivot pools exist. The HTF bias requests
   already use the offset-plus-lookahead pattern correctly. See TradingView's
   [documented non-repainting HTF pattern](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/).
2. **Session highs/lows are chart-bar approximations, not exact session ranges.**
   Lines 108-133 aggregate the entire high/low of a chart bar assigned to a
   session. A 4h bar can straddle a named session's end; 1h bars do not align
   cleanly with 08:30/11:30 boundaries. Out-of-session prices can therefore enter
   the pool. Exact session liquidity requires lower-timeframe aggregation or
   an explicit restriction/approximation label. A limited independent sweep
   reconstruction matched 74/84 displayed sweep price/direction pairs; ten
   remained unresolved. That reconstruction omitted prior-day fallback and
   did not reproduce Pine's session-bar construction exactly, so those ten are
   **not ten proven false signals**, and sweep correctness is not signed off.
3. **Diagnostic directions can be stale.** Lines 570-573 display the remembered
   BOS/sweep/SMT direction, not whether it remains eligible under the six-bar
   age and ordering gates. NQ 4h showed green BULLISH rows while Sweep/SMT and
   BOS + HTF were BLOCK and candidate was NONE. Show ages/expired state or
   label these explicitly as last events.
4. **The main blocker is obscured while a bar is open.** Line 560 prioritizes
   `Bar open`, so every supported chart in this check concealed its more useful
   structural blocker in the compact panel. Separate candle confirmation from
   setup eligibility. On NQ 4h there was no active FVG and daily bias was neutral.
5. **Optional debug drawings are not a clean trading UI.** Enabling proof
   markers and zones produced overlapping labels, historical boxes and a tall
   table covering candles; its bottom row clipped at the initial pane height.
   Boxes retain their original directional color after expiry/mitigation, so
   their presence is not evidence of an active entry zone. All debug toggles
   were restored off. Current strict_v1 uses BOS labels, not BOS line objects;
   zero Pine lines is expected for this revision.
6. **Low frequency is observed, not justified by performance evidence.** All
   eight charts had zero candidates in the most recent 100 bars despite FVG
   retests. The only server-side alert is NQ 4h; changing the visible chart to
   ES or 5m does not expand its coverage. No outcome study was run, and no claim
   about win rate, execution fills, slippage or profitability is supported.

## Display Corrections Applied

- Moved SMC from a large empty standalone pane into the candle/price pane.
- Moved the separate Relative Volume at Time study out of the price pane into
  its own smaller lower pane, without deleting the user's study.
- Reset the scales: the current price had been outside the visible price range.
- Enlarged the price pane, framed recent bars and saved the chart layout.
- Restored NQ 4h, Compact panel, zones off, proof markers off, candidate labels
  on, JSON alerts on and test mode off. Study ID `H3pHcP`, Pine revision 15.0.
- The separate Relative Volume at Time study is not the SMC RVOL formula:
  SMC uses current bar volume / 50-bar average. Different displayed values are
  expected, particularly on an unfinished candle.

## Numerical Checks

For each chart, retrieved the latest 300 OHLCV bars through MCP. Excluded the
unfinished bar when reconstructing FVG/BOS/SMT events. FVG box bounds were
compared with the three-bar gap condition and two-tick minimum. BOS checks
used 3/3 pivots and the two-tick close break; SMT checks used timestamp-aligned
ES/NQ rolling 20-bar extremes. Matching is by marker direction/price, not an
exhaustive timestamp-by-timestamp Pine execution trace. Tie handling, startup
state and all session/day-boundary edge cases are not certified by this check.

| Chart | FVG bounds matched | BOS/SMT markers matched | Computed RVOL | Table RVOL | Retests / setups, last 100 |
| --- | --- | --- | --- | --- | --- |
| ES 5m | 30/30 | 28/28 | 0.233 | THIN | 16 / 0 |
| ES 15m | 30/30 | 28/28 | 3.223 | STRONG | 20 / 0 |
| ES 1h | 30/30 | 18/18 | 1.801 | STRONG | 10 / 0 |
| ES 4h | 30/30 | 10/10 | 0.589 | THIN | 17 / 0 |
| NQ 5m | 30/30 | 24/24 | 0.366 | THIN | 13 / 0 |
| NQ 15m | 30/30 | 20/20 | 2.681 | STRONG | 11 / 0 |
| NQ 1h | 30/30 | 16/16 | 1.743 | STRONG | 11 / 0 |
| NQ 4h | 30/30 | 10/10 | 0.571 | THIN | 23 / 0 |

- All eight tables and companion alignment checks populated; 30 retained labels
  and 30 boxes were accessible per chart with debug toggles on. Zero line objects.
- All eight RVOL classifications matched the independently computed formula.
  Volume is intrabar and changes after the capture.
- Independently calculated ATR/range/efficiency and two-clear-bar pause state
  agreed with INACTIVE consolidation on all eight current bars. This does not
  test a new live transition into/out of consolidation.
- Two retained historical candidate examples had correct SELL price geometry
  and exactly 2.0 RR: ES 5m entry 7437.25, SL 7453, TP 7405.75; NQ 15m entry
  28347, SL 28443.75, TP 28153.5. These are not current recommendations or fills.
- HTF selection was 60m for 5m/15m, 240m for 1h, daily for 4h. Exact EMA
  initialization and every historical HTF transition were not independently
  reproduced.
- Negative control: OANDA:XAUUSD 15m showed `Unsupported chart`, companion BLOCK,
  candidate NONE. Gold is not signal-supported by this ES/NQ policy.
- Local Pine `pine_check`: **0 errors, 0 warnings**. No source was uploaded.

## Hosted Workflow

- Public health: HTTP 200. Unauthenticated dashboard/status: HTTP 401.
- Authenticated hosted dashboard and Processing Status loaded through the
  existing browser session, without retrieving or exposing credentials.
- Database OK; worker RUNNING; service ready; 11 DONE jobs; no pending/failed
  jobs; OpenAI provider configured with `gpt-4o-mini`; notifications DISABLED.
- ES/NQ news CLEAR at inspection. Production still uses the manual calendar.
  Its freshness expires November 9 at **17:47 UTC**, then verified-news
  approvals should fail closed. PR #5 automatic refresh is OPEN, not deployed.
- Operator alert observation is from November 8 at 18:02 UTC, not a live
  TradingView poll. Its 24h observation freshness expires today at 18:02 UTC;
  this audit did not rewrite that record.
- Exactly one active TradingView alert before and after: **6022530375**, NQ 4h,
  Any alert() function call, Pine revision 15.0, expiry January 7, 2027 at
  18:00:21 UTC. JSON on, test off; `last_fired` null. No alert was changed.
- Last natural backend receipt remains October 16 at 14:10:06 UTC, from an
  older alert revision. The current alert was only created November 8.
- Latest decision remains the November 8 controlled HTTP delivery test:
  `live_rollout_delivery_test_20261108T174950Z`, gpt-4o-mini, BUY, confidence 100,
  RR 2, APPROVED. The UI labels it DELIVERY TEST and historical. It is not a
  current entry signal; confidence is model output, not a calibrated win rate.
- No fresh webhook was injected and no natural webhook fired during this audit.
  New-alert end-to-end delivery therefore remains unconfirmed in this session.

## Screenshots

Files remain in `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/`.
These are runtime validation captures; no project code was built in that repo.

- `audit_20261109_initial_nq_4h.png`: broken initial pane arrangement.
- `audit_20261109_nq_4h_clean.png`: final corrected, saved compact chart.
- `audit_20261109_es_5m_diagnostics.png`
- `audit_20261109_es_15_diagnostics.png`
- `audit_20261109_es_60_diagnostics.png`
- `audit_20261109_es_240_diagnostics.png`
- `audit_20261109_nq_5_diagnostics.png`
- `audit_20261109_nq_15_diagnostics.png`
- `audit_20261109_nq_60_diagnostics.png`
- `audit_20261109_nq_240_diagnostics.png`
- `audit_20261109_xauusd_15_unsupported.png`

Diagnostic captures deliberately show debug clutter to document the limitation;
they are not the final saved settings. Representative 5m/15m/1h/4h images were
visually inspected, and the table/drawing objects were inspected in all eight.

## Tests And Follow-Up

Baseline suite: **153 passed, zero failures**, one existing Starlette/httpx
deprecation warning. Final suite after documentation: **153 passed, zero failures**.
These are local backend tests, not evidence of trading profitability.

Next work: correct daily-level mapping; make session-pool precision explicit;
show candle state separately from blockers and age diagnostic events; distinguish
active/mitigated/expired boxes. Add focused boundary/regression tests before
updating the saved indicator. Any server-side alert replacement needs approval
because alerts retain a saved script/input snapshot. Do not lower the score just
to manufacture activity. Deploy/configure automatic news refresh separately,
then gather forward, labelled outcomes before tuning the signal policy.

No trades, replay, broker actions, live OpenAI test calls, secret changes, alert
creation/deletion or production deployment were performed.
