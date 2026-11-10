# News Feed Recovery, November 10, 2026

## Initial Production Observation

The authenticated hosted status endpoint reported the Forex Factory worker's
latest attempt at 12:18:47 UTC failed with `publisher_http_429`. It had four
consecutive failures, no successful refresh, and a persisted next-attempt time
of 20:18:47 UTC. ES/NQ were UNKNOWN and approvals blocked. No forced retry or
TradingView operation was performed. The precise cause of the publisher's rate
limit is unknown; shared Render egress is a possibility, not an established fact.

## Free Replacement

Selected [ShowMyTrades](https://showmytrades.com/docs/api/economic-calendar).
Its documented public API needs no credentials. Only public USD schedule filters
are sent; no setup, user identifier, webhook credential or OpenAI key is sent.
The service permits app use/caching but not resale as a standalone calendar API.

A read-only local request at 17:09 UTC returned HTTP 200 and 64 USD events,
with publication time 17:05:42 UTC and coverage through November 17. Event count
is an observation, not a permanent expectation or completeness proof.

Spot checks against the [BLS November calendar](https://www.bls.gov/schedule/2026/11_sched.htm)
confirmed CPI on November 10 and PPI on November 13 at 08:30 New York time.
The [Federal Reserve calendar](https://www.federalreserve.gov/newsevents/2026-november.htm)
confirmed several corresponding speech windows. One 23:30 UTC November 10 entry
had a different speaker label than the Fed page, although the blocking time
matched. This is a real data-quality limitation, not a fully independently
verified replacement. No provider can guarantee omissions will be detected.

Other free candidates were not chosen where they required new credentials,
omitted scheduled speeches, or documented multi-day schedule correction delays.

## Safety and Deployment

- `NEWS_PROVIDER=showmytrades`, `REQUIRE_VERIFIED_NEWS=true`.
- `NEWS_REFRESH_INTERVAL_MINUTES=15`, `NEWS_MAX_AGE_HOURS=2`.
- Freshness expires from publisher `generated_at`, never a successful fetch or
  the response clock. The adapter caps validity at two hours independently of
  configuration. Assembly freshness cannot prove all upstream sources are live.
- HIGH/MEDIUM USD events and Fed appearances block 30 minutes before/after.
  This is deliberately stricter than interpreting the new provider's HIGH only.
- Missing/stale/ambiguous/malformed coverage blocks approvals. Durable backoff,
  atomic replacement, post-LLM revalidation and mock-LLM fallback stay enabled.
- Provider-specific refresh state preserves the old provider's cooldown/history.
  No schema migration, credentials, paid service or Pine changes are needed.
- No TradingView alert change, order, broker access or paid OpenAI test is part
  of this recovery. Existing alert expiry/snapshot issues are a separate task.

## Verification

Baseline: 183 passing tests. Replacement implementation: 217 passing tests,
zero failures, one existing Starlette/httpx deprecation warning. Includes synthetic
webhook-to-decision tests proving stale and blackout data produce NO_TRADE and
skip the LLM, while a fresh clear fixture processes normally.

Production rollout verification is pending. Do not treat a successful local
probe or test suite as evidence that the Render worker can reach this source.

## Rollback

Keep strict news validation enabled. Switch to manual and provide a newly checked
bounded calendar if the replacement proves unreliable. Forex Factory remains
available only with its own valid snapshot and cooldown; switching providers does
not make an old calendar fresh. No webhook URL or TradingView alert change is needed.
