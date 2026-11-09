# PR #4 Deployment Verification

Verified November 8, 2026, approximately 17:27-17:37 UTC. This records a
deployment verification, not a claim that the signal service is fully armed.
No TradingView alert was created, deleted, renewed or saved during this check.

## Merge and Deployment

- PR: https://github.com/Rakan-Rouchdi/llm-smc-indicator/pull/4
- Merge commit: `2b3e63efb383abff2cb167f1d9047221d3ab5347`.
- Render deployment: `dep-dbob23a9lscs73cqo660`.
- Render reported the matching revision live at 17:28:42 UTC.
- Application version: `0.5.0`.
- Tests before merge and after verification: 110 passed, 0 failed on each run.
  One dependency deprecation warning.
- Public `/health`: HTTP 200. OpenAPI exposes the new operations endpoints.
- Unauthenticated `/dashboard`, `/status`, `/notifications` and
  `/context/news-calendar`: HTTP 401.
- Authenticated dashboard and all three operations endpoints: HTTP 200.
- Database: healthy. Worker: running. Pending/failed jobs: zero.
- New calendar, alert-observation and notification queries work against the
  hosted database. No destructive migration or manual database rewrite was used.

## Controlled Hosted Webhook

Input was `examples/pine_alert_payload_example.json`, with a unique setup ID,
current test timestamps, an explicit test note and `diagnostics.test_mode=true`.
Its prices are sample data, not a current market opportunity.

| Check | Result |
| --- | --- |
| Path | `/webhooks/tradingview?secret=<redacted>` |
| Setup ID | `deployment_pr4_test_20261108T173608Z` |
| Initial response | HTTP 202, `accepted`, `duplicate=false` |
| Measured client round trip | 1,144 ms on a warm service |
| Worker job | DONE, one attempt, no error |
| Persisted fields | Raw payload, parsed setup, context, decision and validator result |
| Model | `deterministic-preflight` |
| Final decision | NO_TRADE, confidence 0 |
| Validator | REJECTED: verified news coverage unavailable |
| OpenAI invocation | Skipped by the preflight safety gate |
| Duplicate submission | HTTP 200, `duplicate=true`; no additional job/decision |
| Latest decision endpoint | Returned this stored test decision |
| Dashboard | Displayed this setup as DELIVERY TEST, NO_TRADE and REJECTED |
| Notifications | No notification enqueued or sent |

An initial request using the local environment's webhook secret returned 401.
The local secret differs from production. Retesting with the existing production
secret succeeded. Neither secret was changed or committed. Do not overwrite the
production secret with the local development value during alert replacement.

This was an HTTP smoke test, not delivery from TradingView. The latest natural
receipt remains October 16, 2026 at 14:10:06 UTC. That historical decision used
`gpt-4o-mini`; the new test deliberately did not call it.

The service recorded two accepted requests (initial and duplicate), with an
application p95 of 797.3 ms. This tiny warm sample excludes proxy/network/boot
time and does not establish reliable delivery within TradingView's deadline.
Idle/cold and concurrent-request measurements remain outstanding.

## Actual Readiness

- `service_ready=true`, but `armed=false`.
- OpenAI is configured with `gpt-4o-mini`; deterministic validation and safe
  fallback remain enabled.
- News context is still mock/UNVERIFIED for ES and NQ. The manual calendar has
  no verified coverage. `REQUIRE_VERIFIED_NEWS=true` correctly prevents approval.
- Notifications are DISABLED. No final-decision delivery destination is armed.
- The dashboard reports alert status UNKNOWN because no operator observation
  has been submitted. This is not an automatic TradingView poll.
- TradingView's UI independently showed the sole project alert as
  `Stopped - Expired`, NQ1!, 4h. Its old snapshot still has score minimum 60.
- Existing alert ID `5647010108` and exact expiry
  `2026-10-18T17:48:44Z` were recorded in the preceding MCP inspection. The UI
  reconfirmed the expired state during this verification; no new ID was created.
- TradingView MCP could not attach in this session. Launch/restart attempts did
  not expose CDP on port 9222. Read-only alert checks were completed through the
  TradingView UI instead. Resolve attachment before an MCP-based replacement.
- The current chart shows strict_v1, minimum score 75, age limit 6, NQ 4h,
  normal candles and delayed CME data. Revision 15 and JSON/test input values
  were verified during the preceding Pine validation; recheck them immediately
  before taking the replacement snapshot.

## Exact Proposed Replacement (Not Executed)

Only replace the expired project alert after explicit user confirmation. Do not
restart its old code snapshot and do not add a second project alert.

| Setting | Proposed value |
| --- | --- |
| Old alert to replace | `5647010108` |
| Alert name | `SMC LLM Candidate Detector webhook` |
| Symbol | `CME_MINI:NQ1!`; account currently resolves `CME_MINI_DL:NQ1!` |
| Interval | `240` / 4 hours |
| Chart | Normal candles, electronic trading hours |
| Script | Current saved `SMC LLM Candidate Detector`, policy `strict_v1` (revision 15 validated previously) |
| Condition | `SMC LLM Candidate Detector -> Any alert() function call` |
| Frequency | Script-controlled `alert.freq_once_per_bar_close` |
| Message | Use dynamic script-generated JSON; do not paste static JSON |
| Webhook enabled | Yes |
| Webhook URL | `https://<existing-render-host-redacted>/webhooks/tradingview?secret=<existing-production-secret-redacted>` |
| Expiry | **January 7, 2027, 18:00 UTC** |
| App notification / toast | Enabled / enabled |
| Email / sound / additional destinations | Disabled |

The Essential plan's UI explicitly says alerts expire after two months.
Open-ended expiry requires an upgrade and was not purchased. The proposed date
is within the current two-month window. Reconfirm the date if approval is delayed.
Record actual expiry after creation and recheck status at least daily; the new
dashboard's operator observation becomes stale after 24 hours.

### Exact Pine Inputs

| Input | Value |
| --- | --- |
| Companion symbol override | Blank (automatic ES companion for NQ) |
| Pivot left / right bars | 3 / 3 |
| Minimum BOS break / FVG ticks | 2 / 2 |
| Sweep buffer / equal high-low tolerance ticks | 1 / 4 |
| SMT lookback | 20 |
| RVOL length / thin / strong thresholds | 50 / 0.70 / 1.50 |
| ATR length / displacement multiple | 14 / 1.0 |
| Consolidation lookback / range ATR / efficiency max | 20 / 2.0 / 0.30 |
| HTF bias timeframe | 60 (auto-escalates to daily on 4h) |
| HTF fast / slow EMA | 50 / 200 |
| Setup expiry bars | 30 |
| Minimum candidate RR / default TP RR | 1.50 / 2.0 |
| Stop buffer ticks | 2 |
| Minimum rule score / confirmation age limit | 75 / 6 |
| Show diagnostic table / panel mode | True / Compact |
| Show FVG zones / proof markers | False / False |
| Show candidate price labels | True |
| Enable alert() JSON payloads | True |
| Enable test webhook alert | False |

## Security and Remaining Work

A browser diagnostic accidentally included dashboard credentials despite an
attempted redaction. They are not repeated here. Rotate the dashboard password
in Render before treating dashboard access as secure. The OpenAI key was not
revealed, changed or used for this smoke test; no webhook secret was printed.
Temporary verification credentials were kept in a mode-0600 runtime file and removed immediately after
loading. No real `.env` was changed; both `.env` paths remain ignored/untracked.

Before a fully armed rollout: rotate the dashboard password; configure and
verify manual news coverage; obtain approval for the alert configuration above;
replace exactly one expired snapshot; record the new ID/expiry; verify a real
TradingView delivery. Notification destination approval and cold-start latency
verification remain separate gates. Never mark an empty calendar as verified
just to get a passing result.

No trades, broker connections or replay tools were used. No TradingView alert
was saved or replaced. This deployment is not evidence of a profitable strategy
or a reliably always-on commercial signal service.
