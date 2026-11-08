# Strict Policy Validation

Date: November 8, 2026.

## Backend

- Baseline: 60 passing tests.
- Final suite: 110 passing tests, zero failures (one existing Starlette/httpx deprecation warning).
- Covered strict feature/sequence/score gates, exact shortened candle close, safe fallback, post-model news recheck, calendar blackout/freshness, alert expiry/stale observation, protected operations routes, outbox delivery/suppression/retry/ambiguity, receipt timing and hosted CLI authentication.
- Tests use temporary SQLite and mock/fake model/network providers. Actual Neon/PostgreSQL migration and outbound notification delivery remain deployment checks.
- Local preview on port 8011: mock provider, notifications off, isolated temporary SQLite, no production data changes. Health/dashboard 200; sample POST 202; mock BUY, confidence 85, RR 2, validator APPROVED. Mock exercises explicitly disable the verified-news requirement. Live defaults fail closed.
- Desktop and 390px mobile dashboard inspected. Fixed raw JSON overflow; final mobile document width equals viewport width (390px).

## Pine

- `pine_check`: zero errors, zero warnings.
- `pine_set_source` and `pine_smart_compile`: updated chart; no compiler errors. Initial editor-open attempt failed; retry succeeded. No claim based on the failed injection.
- Latest saved revision 15; both supported instruments resolve to the account's delayed feed.
- Inspected state, tables, labels, boxes and lines for every combination below. All show the seven-row strict_v1 panel. Zero lines is the intended clean result; zones are disabled by default. Labels are historical candidates across the loaded dataset, not fills or recent alert counts.
- Initial immediate table reads sometimes preceded study calculation. Bounded rereads confirmed the panel before reporting pass.

| Instrument | Minutes | Result | Candidate labels loaded | Lines | Boxes |
| --- | --- | --- | --- | --- | --- |
| CME_MINI_DL:ES1! | 5 | PASS | 2 | 0 | 0 |
| CME_MINI_DL:ES1! | 15 | PASS | 2 | 0 | 0 |
| CME_MINI_DL:ES1! | 60 | PASS | 9 | 0 | 0 |
| CME_MINI_DL:ES1! | 240 | PASS | 2 | 0 | 0 |
| CME_MINI_DL:NQ1! | 5 | PASS | 1 | 0 | 0 |
| CME_MINI_DL:NQ1! | 15 | PASS | 2 | 0 | 0 |
| CME_MINI_DL:NQ1! | 60 | PASS | 10 | 0 | 0 |
| CME_MINI_DL:NQ1! | 240 | PASS | 4 | 0 | 0 |

All final tables reported zero candidates in the latest 100 bars. This is a frequency observation, not backtest performance or a profitability claim. Strictness can reduce alerts further; collect labelled examples and forward outcomes before calibration.

## Screenshots

Originals remain in the MCP screenshot directory. Matrix captures were taken while the Pine editor overlay was open; the compact panel is independently verified through table extraction. The final clean NQ 4h capture closes that overlay and exposes the panel.

Final clean view:

`/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_clean_nq_4h_20261108.png`

Matrix captures:

- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_es_5_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_es_15_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_es_60_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_es_240_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_nq_5_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_nq_15_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_nq_60_20261108.png`
- `/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/strict_v1_final_nq_240_20261108.png`

## Live Cutover Not Completed

Alert 5647010108 remains inactive and expired. No alert was modified. The hosted backend remains on its prior revision until this branch is deployed. Verified manual news coverage and a notification destination are not configured by this work. Hosted cold-path webhook latency is not yet measured with the new instrumentation. Follow [strict_policy_rollout.md](strict_policy_rollout.md) before claiming the system is armed.

