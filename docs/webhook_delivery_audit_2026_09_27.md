# Webhook Delivery Audit: September 27, 2026

## Confirmed incident

Exactly one TradingView alert exists: `5647010108`, active on `CME_MINI_DL:NQ1!`, 4h, Pine snapshot 13.0, test mode disabled. Its last trigger was September 24 at 18:10:00 UTC. TradingView's log says: "Webhook delivery failed - request took too long and timed out."

The webhook was not lost. Neon contains setup `CME_MINI_DL:NQ1!_240_1790258400000_38471`, received at 18:10:06.931956 UTC. OpenAI model `gpt-4o-mini` produced a decision at 18:10:18.304660 UTC. The final action was `NO_TRADE`; the validator recorded `Setup is stale; LLM chose NO_TRADE`. The LLM itself cited weak confluence and confidence below threshold. This audit does not overwrite that historical result or retrospectively approve it.

## Root causes

1. The webhook handler ran OpenAI synchronously before responding. Processing took approximately 11.4 seconds after receipt, exceeding TradingView's [three-second deadline](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/). The original PRD required a quick acknowledgement and queued processing; the implementation did not satisfy that requirement. Earlier mock-only endpoint tests did not detect the timing error.
2. Pine's `bar_time` was 14:00 UTC, the OPEN of the 4h candle. The backend incorrectly measured age from that opening timestamp. At 18:10 it counted about 250 minutes, although the candle had closed about 10 minutes earlier.
3. Dashboard pages required authentication, but `/setups`, `/decisions/latest` and outcome APIs did not. Raw setups and decisions could be read without the dashboard login, and outcome records could be written without it.
4. Uvicorn's default access logs included webhook query strings. Application access-log filtering now removes query strings. Hosting-provider edge logs are outside this application filter.

## Repairs

- Validate and commit the alert plus a `decision_jobs` record before returning HTTP 202.
- Process OpenAI and deterministic validation in a separate worker thread using fresh database sessions.
- Recover persisted jobs after restarts through expiring leases, prevent duplicate jobs via setup ID uniqueness and bound unexpected-failure retries to three attempts. Error records contain only exception types, not credentials or SQL.
- Measure supported intraday setup age from candle close; send the same timing context to the LLM. Recalculate age after the LLM finishes for deterministic validation.
- Apply dashboard authentication to setup, decision, outcome and operational-status APIs.
- Show the most recently received setup even while it is queued or failed, instead of presenting a previous decision as if it belonged to the new setup. Show receipt and decision timestamps and processing errors.
- Keep `/health` as public process liveness. The protected `/status` endpoint checks the database, worker and job counts.

No Pine trading rules, alert thresholds, alert inputs or TradingView alert definitions were changed. No trades, broker connections or replay trading were used. OpenAI credentials were not read, printed, changed or committed. Existing webhook/dashboard credentials were used privately for hosted checks.

## Signal frequency and remaining limitations

- Only NQ 4h is monitored by the one live alert. Validating ES and other timeframes earlier did not create live alerts for them.
- The chart shows 17 FVG retests and 2 candidate setups over the last 100 loaded 4h bars. One trigger over the past week is plausible under these filters. This small sample does not establish an expected weekly rate, profitability or useful signal quality.
- TradingView explicitly reports delayed data. This alert fired 10 minutes after the candle close. Delivery repairs cannot make that feed real time.
- News and Telegram context are still mocked. The backend is not checking actual upcoming economic-news blackouts.
- Render Free may sleep or restart, and Neon may require a cold wake. [Render documents free-service spin-down](https://render.com/docs/free). Even a fast application acknowledgement cannot guarantee a response within three seconds during those events. An uptime check does not prove the full webhook path works.
- The worker sleeps when idle to avoid continuously waking Neon. The supported deployment is one web process with one worker thread; separate worker infrastructure is needed before scaling horizontally. Unclaimed jobs are scanned at startup and hourly, with immediate notification on new receipts and earlier wakes for retry/lease deadlines.
- Legacy Pine v13 does not supply an exact close timestamp. The backend supports the validated 5/15/60/240-minute periods and conservatively rejects a shortened session bar if its nominal close is still in the future. A later payload revision can supply `diagnostics.bar_close_time` without changing setup logic.
- The alert expires October 18, 2026 at 17:48:44 UTC. It still needs renewal before then.

## Validation

- Initial suite: 46 passed.
- Repair suite: 60 passed, including a blocked LLM with a sub-second local acknowledgement, durable receipt recovery, expired leases, bounded failure retries, duplicate suppression, timestamp regression cases, protected data routes and visibly labelled delivery tests.
- Before deployment, authenticated hosted dashboard returned 200 and displayed the real September 24 setup. A duplicate delivery probe returned 200/duplicate in 0.699 seconds and did not create a new decision.
- The saved TradingView alert's HTTPS host, endpoint path and secret matched the backend. Secret equality was checked using a private fingerprint comparison; no credential value was displayed. The alert was inspected and cancelled without saving changes.
- UptimeRobot's authenticated monitor page and monitor list returned an unexpected-error screen. Its historical uptime could not be verified. Render runtime logs did show continuing `HEAD /health` requests in addition to Render's own health checks.
- Hosted repair verification is recorded below after deployment.

Full hosted URLs, webhook secrets and dashboard credentials are intentionally omitted.
