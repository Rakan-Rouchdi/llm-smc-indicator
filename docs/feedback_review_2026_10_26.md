# SMC Feedback and Reliability Investigation

Date: October 26, 2026

## Scope and decision status

Reviewed all three pages of the user-supplied `SMC INDICATOR .pdf`, current Pine/backend code, the existing PRD, today's live status audit, and official platform documentation. The PDF is proposed feedback, not authorization to change the live service or alert. No Pine source, TradingView alert, hosting configuration, credentials, or trading behavior was changed during this review. No trades or broker operations were performed.

The proposed MRKR name (pronounced MARKER) is recorded as a branding option only. No rename, domain purchase, or name-availability claim is included.

## Executive findings

1. The only TradingView alert, `5647010108`, expired October 18. It remains inactive. A healthy backend cannot compensate for a stopped source alert.
2. Seven natural alerts since the September 27 audit reached storage and completed with `gpt-4o-mini`: two BUY, two SELL, three NO_TRADE. Four were marked delivered by TradingView; October 8, 9, and 16 were marked timed out despite being stored. All seven jobs completed once without fallback. This is evidence of processing, not evidence of profitability or reliable acknowledgement.
3. Two NO_TRADE decisions hit the documented shortened-session candle limitation. The backend already accepts an exact closing timestamp, but Pine does not send one. This now has observed consequences, not just theoretical risk.
4. The score is already bounded to 0-100. The panel displays `score/minimum_threshold`, misleadingly suggesting a maximum of 60. Zero means no directional active FVG, not necessarily a frozen calculation.
5. The backend's deterministic validator checks price geometry, freshness, consolidation, blackout, direction and LLM confidence, but does not independently enforce the chart's required confirmations. An offline schema-valid setup with score 0, no FVG/BOS/sweep/SMT, thin volume and opposite HTF bias was still APPROVED when paired with a valid, confident BUY output. This is a reproduced policy gap, not a claim that such a malformed candidate was received in production.
6. Real news handling and final-decision push notifications are not implemented. Context is hard-wired to mock adapters; the notifier is a no-op.

## Feedback disposition

| PDF proposal | Evidence and diagnosis | Proposed response |
| --- | --- | --- |
| 1. Cleaner chart, buy/sell with TP/SL | The indicator retains up to 90 lines, 90 boxes and 90 labels. MCP reported 90 lines on the current chart. Chart markers are provisional Pine candidates, not backend-approved decisions. | Default to one concise candidate marker with numeric entry/SL/TP and subtle consolidation shading. Separate development diagnostics from the user view. Keep the provisional label explicit. |
| 2. News awareness and working alerts | `build_context()` always constructs mock adapters. News tables exist, but there is no working ingestion/lookup path. `NoopNotifier.send()` does nothing and is not called by the workflow. | Add a verified calendar adapter and deterministic backend blackout gate. Add a durable notification outbox after final validation. Distinguish TradingView candidate delivery from final approved-decision notifications. |
| 3. Smaller panel | The current table has 20 rows, including low-level debug gates and historic feature states. A previous BOS/SMT status can be displayed after its eligibility age has expired. | A compact default panel of about six rows: state/direction, score and threshold, main blocker, HTF/session, latest provisional risk levels, and candle status. Keep expanded diagnostics optional. Do not claim backend/news/alert health is known inside Pine. |
| 4. Minimise lag | Alerts intentionally require confirmed bars. Pivots require three right-hand bars by default; HTF bias uses a completed higher-timeframe candle. The live feed is delayed. Rendering clutter and transport latency are separate issues. | Preserve confirmed-bar alerts; optionally show clearly marked live previews without alerting. Profile before optimizing. Measure feed, confirmation, transport, database and LLM delays separately. No promise of zero-lag non-repainting signals. |
| 5. Consolidation blocking | Pine already includes `not consolidationActive` in both candidate rules; the backend also rejects consolidation. The detector is a conjunction of range compression and low efficiency, not a universal range detector. | Preserve the hard block. Validate classification against labelled ranges/trends on all supported timeframes. Consider a confirmed-bar state machine with explicit exit confirmation if tests justify it. Do not replace AND with OR without measuring false blocks. |
| 6. Repair score and use 0-100 | Positive weights sum to 115 and are clipped to 100. The table shows `directionalScore/minRuleScore`; it returns 0 without an active FVG. The live table showed 55/60, disproving a currently frozen-zero display. | Show `55/100` and separately `minimum 60`; show `No active setup` instead of a misleading zero. Keep cosmetic changes separate from policy changes. If weights change, use a versioned 100-point rubric and recalibrate thresholds on historical and forward samples. |
| 7. Remove green/red lines | BOS lines extend indefinitely right; candidate entry/SL/TP lines extend 30 bars and accumulate. Candidate drawings use `selectedCandidate`, while alert deduplication uses a different flag, allowing repeated drawings for one FVG. | Remove the obstructive BOS and trade-level lines, not merely recolor them. Retain levels as compact numeric labels/panel values. Ensure one marker per setup independent of whether webhook emission is enabled. Clarify whether "both versions" means clean/debug views; currently there is one Pine implementation. |
| 8. Strongest confirmations only | Current eligibility is `(sweep OR SMT) AND (BOS OR aligned HTF)` plus other gates. BOS can allow a counter-HTF candidate; HTF can substitute for BOS. Events can remain eligible for 30 bars. The code does not enforce the PRD's suggested BOS-after-liquidity-event sequence. | Define and version an explicit strict policy. Require hard gates independently of score, associate evidence with the same setup leg, bound its age, and mirror policy-consistency checks in the backend. More confirmations do not establish a higher win probability without outcome evidence. |

## Confirmed source locations

- `pine/smc_llm_candidate_detector.pine:87`: retention limits.
- `pine/smc_llm_candidate_detector.pine:113`: session classification using the chart bar's opening time.
- `pine/smc_llm_candidate_detector.pine:146`: delayed pivot confirmation.
- `pine/smc_llm_candidate_detector.pine:179` and `:187`: right-extending BOS lines.
- `pine/smc_llm_candidate_detector.pine:304`: rolling-window SMT approximation, not pivot-aligned SMT.
- `pine/smc_llm_candidate_detector.pine:351`: consolidation detector.
- `pine/smc_llm_candidate_detector.pine:368`: completed HTF values.
- `pine/smc_llm_candidate_detector.pine:380`: provisional stops; prior sweep anchors are retained independently of the current FVG.
- `pine/smc_llm_candidate_detector.pine:391`: weights, clipping and candidate gates.
- `pine/smc_llm_candidate_detector.pine:440`: candidate drawings and risk lines.
- `pine/smc_llm_candidate_detector.pine:484` and `:529`: natural/test diagnostics omit exact close time.
- `pine/smc_llm_candidate_detector.pine:545`: 20-row table and ambiguous score denominator.
- `backend/app/timing.py:20`: nominal close calculation and existing exact-close support.
- `backend/app/validators.py:88`: deterministic checks and missing feature-eligibility checks.
- `backend/app/workflow.py:109`: database receipt/job transaction before acknowledgement.
- `backend/app/main.py:157`: protected status checks database/worker, not alert expiry or ingress latency.
- `backend/app/context.py:42`: unconditional mock adapters.
- `backend/app/notifier.py:4`: no-op notification implementation.
- `backend/scripts/check_mvp_status.py:108`: old helper assumes unauthenticated routes and local SQLite; it is not a valid hosted Neon health check.

## Reliability work carried forward

### A. Exact candle-close timestamp

Send `diagnostics.bar_close_time` as a UTC ISO timestamp from Pine's `time_close` variable in both natural and test payloads. Preserve `bar_time` as the opening time for compatibility. Also include a script/policy version and, if useful for latency tracing, a separately named emission timestamp from `timenow`.

The schema permits diagnostic fields and the backend already supports `bar_close_time`. Do not change the opening timestamp's meaning, extend freshness limits to hide the error, or rewrite historical decisions.

Offline reproduction for an opening time of October 6, 18:00 UTC and evaluation at 21:11 UTC:

- Legacy nominal 4h close: 22:00, computed age **-49 minutes**, rejected.
- Explicit shortened close of 21:00: computed age **11 minutes**, within the current 15-minute age policy.

TradingView documents [bar opening/closing timestamps](https://www.tradingview.com/pine-script-docs/concepts/time/) and [session-boundary behavior](https://www.tradingview.com/pine-script-docs/concepts/sessions/). Use the actual chart `time_close` variable, not a guessed duration or a custom-session function accidentally measuring a different bar.

Acceptance: normal 5m/15m/1h/4h bars, shortened session bars, DST changes, malformed/future close timestamps, legacy payloads, test mode, schema validation and Pine compilation. A timing regression test alone is insufficient: verify the actual compiled Pine payload carries the new field.

### B. Remaining acknowledgement delays

The previous synchronous-OpenAI problem is fixed. The current handler still waits for database connection/check-out, duplicate lookup and durable receipt/job commit. This is necessary for the current durability design; acknowledging before that commit would risk silently losing signals.

Current evidence does not isolate which part exceeded the deadline in October. `received_at` is assigned during database insertion; it is not a request-arrival or response-sent timestamp. Differences between TradingView's trigger time and that timestamp cannot prove a particular network/database cause.

Add secret-safe timings for request ingress, validation, connection acquisition, duplicate lookup, durable commit, response send, worker start, provider duration and final persistence. Correlate by setup ID/request ID, never by full URL or secret. Measure warm and idle/cold cases, duplicates, failures and concurrent requests against the actual hosted database.

TradingView's [documented deadline is three seconds](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/). Aim for a durable acknowledgement comfortably below that threshold, not just a successful health response. [Render Free can spin down](https://render.com/docs/free); [Neon can suspend and reconnect](https://neon.com/docs/introduction/compute-lifecycle). These are plausible risks, not proven causes of the three specific incidents.

Optimize proven bottlenecks first. If measured cold-path latency cannot reliably fit the deadline, use always-on ingress/storage or a separate durable queue whose acknowledgement fits the budget. Upgrading only the web process does not eliminate database wakeup or network delays. Do not use ephemeral Render filesystem writes or an in-memory background task as the sole receipt store.

### C. Alert renewal and monitoring

Do not simply resume the expired old snapshot and assume it contains a new Pine fix. TradingView stores a [snapshot of code, inputs, symbol and timeframe](https://www.tradingview.com/pine-script-docs/concepts/alerts/). Prepare and compile the revised payload first, then request approval for replacing the stale alert with exactly one updated NQ 4h alert. Preserve the current hosted endpoint/authentication, use dynamic `alert()` messages, enable JSON alerts, disable test mode and record the new expiry/ID.

Monitoring needs separate signals:

- Service liveness (`/health`).
- Protected database/worker readiness and oldest pending-job age.
- Durable webhook acceptance latency and errors.
- Last natural receipt and decision, clearly separated from delivery tests.
- Expected alert ID, symbol/timeframe, expiry and last verified status.
- Missing or stale monitoring data, not a falsely green state.

A quiet market is not proof of failure. Track expiry explicitly and surface stale observations as UNKNOWN. Without a continuously connected authorized TradingView observer, the backend cannot discover current alert status from the absence of webhooks. A local MCP poll stops when the machine/app is off; a registered expiry can still drive reminders from hosted infrastructure. No automatic renewal, new monitor or recurring task was created in this review.

UptimeRobot social login currently reports an account/email conflict. Restore access separately. Its health pings alone do not verify the signal pipeline. Update the old CLI helper to use authenticated hosted `/status` rather than inspect an unrelated local SQLite file.

## Signal policy and product boundaries

### Proposed strict policy, not yet approved

Use a versioned policy with explicit rejection reasons. A first strict-policy specification should require:

1. A confirmed time-based chart bar with a valid opening/closing timestamp.
2. Sufficient data, aligned companion timestamps and bounded feature ages.
3. A still-valid directional FVG and a confirmed retest; reject invalidated zones.
4. Recent directional liquidity evidence (sweep or SMT) and confirmed structure in the documented sequence, associated with the same setup leg.
5. Aligned HTF bias rather than allowing BOS to override an opposite HTF bias.
6. Non-thin volume and no active consolidation.
7. Coherent entry/SL/TP, positive risk and minimum RR, with an explicit pending-entry/expiry policy.
8. Minimum confirmation score after the hard gates, and one event per setup.
9. Backend freshness, verified-news availability/blackout rules, valid LLM output and deterministic final approval before user-facing final notifications.

Exact lookbacks, score weights, displacement requirements and threshold values require validation, not arbitrary tightening. Requiring displacement on the retest candle itself may discard legitimate retracements; consider evidence on the formation/structure leg instead. Strictness can make signals even less frequent.

The server can check consistency of submitted feature facts but cannot independently verify OHLCV truth without a market-data source. Keep this distinction explicit when describing deterministic validation.

Further quality issues worth testing before claiming strong confirmation:

- A 30-bar feature lifetime spans very different wall-clock periods on 5m and 4h. Old SMT/BOS evidence may be unrelated to the current zone.
- Provisional TP is algebraically set to `defaultRR * risk`; passing RR=2 does not prove a realistic reachable target or adequate liquidity room.
- A candle can touch the entry intrabar and close far beyond it. A later webhook must not be treated as an already-filled trade. Track pending entry, invalidation and outcome assumptions before calculating performance.
- Session labels are based on bar opening time; a 4h bar can straddle named sessions. Distinguish formation-session context from emission time, rather than treating OFF_HOURS as proof the alert fired outside the session.
- Keep mock fallback for testing, but do not silently distribute mock fallback BUY/SELL decisions as live-LLM-approved notifications. Persist provenance and choose an explicit production fallback policy, preferably hold/NO_TRADE for final push delivery.

### News integration

Pine's [documented external-data functions](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/) do not provide a general arbitrary-HTTP backend callback. `request.economic()` supplies economic metric series, not a complete scheduled high-impact-event calendar or headline feed.

Recommended incremental implementation:

- Wire the existing event/headline tables to an authenticated manual-calendar ingestion path first, as already anticipated by the PRD. Include source, verification time, timezone, affected instruments, impact, blackout window, and coverage/freshness status.
- Then add a licensed live calendar adapter behind the same interface after checking cost, update latency and redistribution rights. Do not infer an empty calendar means no risk when the feed failed.
- Apply the news gate before the LLM call where possible, and recheck before final approval/notification. The LLM may explain supplied headlines; it must not invent events.
- Treat UNKNOWN/stale/unavailable news distinctly from clear. In strict live mode, suppress final BUY/SELL notifications until required context is verified.
- Pine may still emit provisional candidates during a backend news blackout. The backend suppresses final approval; it cannot retract existing Pine markers. Optional manually configured Pine blackout windows have snapshot/maintenance limitations and are not equivalent to live news integration.

### User-facing notifications

The current alert is a machine-to-backend candidate webhook. Final-decision push delivery requires real implementation, not a UI toggle. Add a persistent notification outbox keyed by decision/recipient/channel, bounded retries, error visibility and duplicate suppression. Send only newly approved, fresh, non-test decisions under the chosen provider/news policy. Keep database decisions even if notification delivery fails. Do not replay historical BUY/SELL records as new alerts.

## Suggested implementation order

1. **Reliability and policy safety:** exact close timestamps; negative validator fixtures; versioned feature gates; explicit fallback/test provenance; secret-safe receipt timings. Compile and verify candidate payloads without changing the existing trading rules accidentally.
2. **Restore one live alert:** after approval, replace the expired snapshot using the compiled payload revision; verify one active alert and a controlled delivery path. Record expiry and establish operational monitoring. Do not wait for a full cosmetic redesign to restore data collection.
3. **Chart clarity:** remove obstructive lines, deduplicate markers, compact/expanded panel, honest 0-100 score plus separate threshold, invalidation/expiry state. Keep the clean/debug views on one shared detection implementation.
4. **News and final notifications:** verified calendar ingestion, fail-closed live policy where appropriate, notification outbox and delivery checks. No claim of news-aware signals before these are connected.
5. **Evaluate, then brand/release:** labelled chart cases, out-of-sample/forward observations and entry/outcome accounting. MRKR can be adopted separately; rebranding does not resolve reliability or signal-quality gaps.

## Verification performed

- PDF text extracted and all three rendered pages inspected.
- Current chart inspected through MCP; 90 retained lines confirmed; score was 55/60, not frozen at zero.
- Existing suite: **60 passed, 0 failed**, one existing Starlette/httpx deprecation warning.
- Offline feature-gate counterexample: schema validation passed; validator returned APPROVED/BUY with confidence 76 despite score 0, absent confirmations, thin volume and opposite HTF.
- Offline shortened-close calculation: -49 minutes using nominal duration versus 11 minutes using explicit close.
- No new live OpenAI call or synthetic production webhook was sent during this PDF review. Earlier same-day live status evidence is reported separately from these offline reproductions.
- No source-code fix or deployment is claimed by this document. The reproduced gaps need new regression tests; the 60 currently passing tests do not cover them adequately.

The API screenshot attempt did not return a saved artifact. The inspected CDP chart capture is at `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/smc_feedback_review_20261026.png`; TradingView onboarding overlays obscure part of it, but line clutter and the score/table remain visible. Original screenshots were not moved.
