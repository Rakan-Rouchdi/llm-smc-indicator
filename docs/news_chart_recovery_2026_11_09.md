# News Retry Recovery And Final Chart Checks

## Operational Result

The free calendar is **not yet restored**. The last hosted request at
`2026-11-09T22:18:44Z` received `publisher_http_429`. There is no successful
automatic snapshot or publisher timestamp in production. ES and NQ remain
UNKNOWN and approval is blocked. No freshness timestamp was fabricated, no
mock-news fallback was enabled, and no alternate hostname/proxy was used.

Render successfully deployed `a7b4b61` (including backend fix `0805de3`).
Public health returned 200, unauthenticated dashboard returned 401, and the
authenticated dashboard displayed the rate-limit warning and next attempt.
The database and decision worker are healthy, with zero failed jobs.

The durable next retry is `2026-11-10T00:18:44Z`. This is an earliest attempt
deadline, not a recovery guarantee. The worker needs to be running; Render Free
can sleep. Restarting/deploying does not bypass this deadline. A successful
hosted fetch with genuinely fresh publication/coverage must still be observed
before declaring automatic news operational.

The user chose to remain free. No paid provider, hosting upgrade or credential
was added. If the publisher continues rejecting requests, the safe free fallback
is a genuinely verified manual calendar, not an automated claim of completeness
from a partial calendar. That fallback reintroduces maintenance. A free feed
without an availability agreement cannot honestly be promised reliable.

## Retry Changes

- Added `calendar_refresh_schedule`, an additive SQLite/PostgreSQL table with
  next-attempt deadline, attempt identity and consecutive failure count.
- Atomic conditional claims prevent duplicate requests from overlapping workers.
- Failures back off to 2/4/8 times the normal interval; a later valid HTTP
  `Retry-After` deadline takes precedence. The schedule survives restarts.
- Successful fetches reset backoff, but publisher `Last-Modified` still controls
  data freshness. Retrying an old publication does not renew coverage.
- Superseded attempts cannot overwrite a newer snapshot or clear its state.
- Dashboard/status show the next attempt and a readable HTTP 429 explanation.
- No change to deterministic preflight/postflight news checks, threshold policy,
  LLM fallback or webhook authentication.

## Chart Verification

Pine revision 19 compiled through TradingView with **0 errors, 0 warnings**.
It only adds opaque diagnostic cell/frame borders to revision 18. Transparent
one-pixel border gaps had allowed candle wicks to show through despite opaque
cells and the indicator being at the front. No trading detection logic changed
in this follow-up. Earlier timing/session fixes are documented in
`docs/timing_session_fixes_2026_11_09.md`.

At approximately 22:29 UTC, all eight ES/NQ combinations (5m, 15m, 1h, 4h)
returned populated diagnostic tables, 30 retained proof labels, 30 FVG zones,
and no Pine line objects. Current code uses BOS labels, not `line.new` trails.
All tables reported CLOSED, OFF_HOURS, COMPLETE minute coverage and Candidate
NONE. The account was showing delayed data and a closed market. These are
closed-market rendering/data checks, not a new live alert or profitability test.

Independent aggregation of complete five-minute candles matched the panel:

| Symbol | NY AM low/high (13:30-16:30 UTC; 36 bars) | NY PM low/high (18:30-21:00 UTC; 30 bars) |
| --- | --- | --- |
| ES | 7455.75 / 7564.50 | 7563.50 / 7600.50 |
| NQ | 27268.00 / 28014.75 | 27924.00 / 28129.25 |

The 5m/15m/1h panels use the completed NY PM pool. The current 4h bar uses NY AM,
which was the completed pool available before that parent bar began. This
intentional difference prevents using a later session retroactively for a sweep.
Prior-day values also agree across all four timeframes for each symbol.

Debug proof labels can overlap each other at dense historical locations. They
are off in the normal Compact layout. `ORDER BLOCK` in an event-status row means
the event is ineligible by timing/order; it does not implement an SMC order-block
zone. These are remaining presentation limitations, not trade approvals.

All eight matrix screenshots were visually inspected and the table border fix
is visible. Files remain at
`/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/`:

- `news_recovery_20261109_{ES,NQ}_{5,15,60,240}.png`
- `news_recovery_20261109_NQ15_diagnostics.png` (before opaque-border fix)
- `news_recovery_20261109_NQ15_opaque_borders.png` (after fix)

The Mac locked again after the matrix. MCP confirms the chart was restored to
NQ 240, Compact, zones/proof markers false, candidate labels true, JSON true,
test false, and the editor was closed; the layout reports All changes saved.
However, captures made while locked retained stale canvas content despite the
updated inputs. Files with `compact_final`, `compact_saved` or `clean` in their
names from that locked period are NOT valid evidence of the final compact view.
After the user unlocked the Mac again, the final Compact view was visually
verified at approximately 22:59 UTC: eight readable rows, no debug labels/zones,
editor closed, test mode false, JSON alerts true, revision 19, NQ 4h, and native
layout status All changes saved. The table showed WAIT / Await retest, CLOSED,
55/100 (minimum 75), daily HTF NEUTRAL and OFF_HOURS. Native inspection confirmed
the temporary TradingView table-hover controls disappeared and did not obscure
the final panel. The final-layout blocker is resolved.

Final evidence: `news_recovery_20261109_NQ4h_verified_compact.png` in the same
screenshot directory. Earlier locked-period captures remain invalid evidence;
they were not silently overwritten. The alert was rechecked read-only and
remains exactly one active revision-15 alert with test mode false.

## Alert And Backend Safety

Read-only listing: exactly one active alert, ID `6022530375`, delayed NQ 4h,
revision 15, score 75, age 6, JSON true, test false, last_fired null. Expiry is
`2027-01-07T18:00:21Z`. No alert was created, deleted, edited or resnapshotted.
Chart revision 19 does not automatically update the server-side alert snapshot.

The dashboard's alert status is UNKNOWN because its separate operator
observation is older than 24 hours, not because the MCP found an inactive alert.
Latest backend decision remains the historical November 8 delivery test,
gpt-4o-mini BUY/APPROVED. No new webhook or paid LLM test was sent in this work.
No trades, broker connection, replay, credential changes or secret commits.

Final proposed alert configuration remains in
`docs/timing_session_fixes_2026_11_09.md`, now referencing revision 19. It is
only a proposal. Keep the alert unchanged until the user separately approves.

## Tests

Baseline: 167 passed. Updated suite: **183 passed, 0 failed**, one existing
Starlette/httpx deprecation warning. New coverage includes Retry-After formats,
safe error metadata, persistent capped backoff, legacy cooldown migration,
overlapping workers, stale-result exclusion and dashboard/status rendering.
HTTP/provider responses in pytest are mocked; hosted recovery is not proven by
these tests. Real PostgreSQL startup/status verified the additive schedule table;
concurrency tests themselves ran on SQLite.

Desktop dashboard warning and retry time were visually checked. The mobile
viewport override did not take effect while the Mac was locked, so no mobile
visual pass is claimed. Static design scan flagged four pre-existing detail-row
padding warnings outside the changed status paragraphs; no redesign was made.
