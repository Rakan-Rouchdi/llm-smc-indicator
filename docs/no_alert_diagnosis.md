# Sparse TradingView Alerts: September 18, 2026

## Observed state

- The hosted backend `/health` returned HTTP 200.
- The latest hosted decision was still the controlled ES 5m test from September 6, 2026; no newer setup was stored.
- TradingView MCP reattached after an old desktop process without CDP was stopped and TradingView relaunched through `tv_launch`.
- Exactly one TradingView alert was listed: ID `5262922741`, active on NQ 4h, expiring October 6, 2026. TradingView reported its last trigger as August 24, 2026.
- The chart indicator was hidden, which concealed its diagnostics. It was made visible and the chart layout was saved. Hiding a chart study is not evidence that its server-side alert stopped.
- The old chart diagnostics showed a mitigated FVG and no current candidate. The alert uses a saved Pine snapshot with a 60-minute bias input on a 4-hour chart.

## Change made

- `pine/smc_llm_candidate_detector.pine` now uses the PRD's 60-minute default on lower charts, but automatically selects a genuinely higher timeframe when the selected input is not above the chart. NQ 4h resolves to daily.
- The chart table now shows each candidate gate, the current bar state, and FVG retests / candidate setups over the most recent 100 bars.
- Candidate thresholds, the JSON alert payload, the backend, and the existing TradingView alert were not changed.
- The script compiled with zero errors and zero warnings and the updated chart table was inspected through MCP.

At inspection, the open NQ 4h bar had a bearish FVG retest and aligned sweep/SMT, but the BOS/HTF gate was blocked and its score was 55/60. The updated script counted 17 FVG retests and 2 candidates in the most recent 100 bars. These are chart-history diagnostics, not evidence of live webhook deliveries.

## Remaining activation step

This was the state at the time of diagnosis. The approved replacement was completed later on September 18; see `docs/alert_replacement_2026_09_18.md`. The new alert still uses NQ 4h. A shorter timeframe could increase candidate opportunities, but that would change signal frequency and requires a deliberate choice.

No alert was created or deleted, no replay or trade tools were used, and no broker was connected.

## Evidence

```text
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/smc_no_alert_diagnosis_2026_09_18.png
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/smc_candidate_gate_diagnostics_2026_09_18.png
```
