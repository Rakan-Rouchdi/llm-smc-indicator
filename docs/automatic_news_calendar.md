# Automatic Scheduled-News Coverage

## Status and Scope

Forex Factory was deployed and enabled on November 9, 2026, after PR #5 was merged. The first
Render-side fetch failed with `HTTPStatusError`; a controlled retry confirmed
`publisher_http_429` (rate limiting). No successful automatic refresh has yet
been verified for that provider. Production correctly reported ES/NQ UNKNOWN and blocked
approvals. See
`docs/timing_session_fixes_2026_11_09.md` for rollout evidence and limitations.

The replacement is [ShowMyTrades' public calendar API](https://showmytrades.com/docs/api/economic-calendar),
without an account or API key. It covers scheduled USD releases and central-bank
appearances. Only ES/NQ are supported here; gold is still not an approved instrument.
The request includes all impact levels. This adapter conservatively blocks both
HIGH and MEDIUM, plus Fed-labelled events, because provider impact scales differ.
All blocking events keep the configured 30-minute-before/after window. Holidays
are not by themselves evidence of an economic-news blackout.

Forex Factory remains selectable for rollback, not an automatic fallback chain.
No host rotation, proxy, bypass or extra request to its rate-limited endpoint is
used to implement the replacement. See `news_feed_recovery_2026_11_10.md` for
deployment evidence and source spot checks.

"Source-validated" means known HTTPS source, strict parsing, bounded declared
coverage and publisher freshness checks. It does NOT mean each event is
independently corroborated against primary agencies. An incomplete but structurally
valid publisher feed cannot be detected reliably. No breaking-news, earnings,
global systemic-risk or gold coverage guarantee is implied. The feed has no
contractual SLA here; review provider licensing before customer redistribution.

## Enable After Deployment

Set these non-secret variables in Render after deploying the code:

```dotenv
NEWS_PROVIDER=showmytrades
REQUIRE_VERIFIED_NEWS=true
NEWS_MAX_AGE_HOURS=2
NEWS_REFRESH_INTERVAL_MINUTES=15
NEWS_FETCH_TIMEOUT_SECONDS=10
```

Keep all existing database, webhook, dashboard and OpenAI settings unchanged.
No new secret is required. The default provider remains mock for new local
installs. The Render Blueprint selects `NEWS_PROVIDER=showmytrades` with strict coverage
required; failure never falls back to mock news or renews the manual snapshot.

The lifespan-managed thread checks on process startup and follows a durable
next-attempt deadline. A conditional database claim prevents simultaneous fetches
across overlapping deployments. Keep the existing single Uvicorn worker/replica;
this guard is not an always-on scheduling service. The additive
`calendar_refresh_schedule` table stores the deadline, attempt identity and failure
count; existing `calendar_refresh` metadata is retained. Rows are provider-scoped
(Forex Factory id 1, ShowMyTrades id 2), so errors/publication versions never leak
across a switch. A snapshot from another provider cannot certify current coverage.
Both tables are created
by startup metadata initialization on SQLite/PostgreSQL; no existing table ALTER
or destructive migration is required.

Failures back off to 2, 4, then 8 times the configured interval (2/4/8 hours with
the old 60-minute interval; 30/60/120 minutes with the new 15-minute interval).
A valid publisher `Retry-After` HTTP date or
seconds value takes precedence when later. Backoff survives process restarts;
success restores the normal interval. An old in-flight attempt cannot overwrite
a newer attempt's result. Upgrading seeds the deadline from the previous attempt,
including a conservative two-interval delay after a recorded failure. Deploying
or restarting is not a way to force another publisher request.

The thread runs only while the service process runs. [Render Free can spin down](https://render.com/docs/free#spinning-down-on-idle);
it is not an always-on scheduler. After wake-up/restart, stale data remains blocked
until a valid refresh succeeds. Uptime checks are not an availability guarantee.
For reliable unattended use, move to always-on hosting or a separately scheduled
authenticated ingestion service; do not relax the stale-data rule.

## Fail-Closed Rules

- ShowMyTrades freshness uses its `generated_at`, never HTTP Date, `server_time`
  or local download time. It describes publisher assembly time, NOT proof of
  successful checks of every upstream source. Its lifetime is capped at two hours
  even if the operator accidentally configures a longer lifetime. Forex Factory
  continues using HTTP `Last-Modified` with its configured age limit.
  Re-fetching the same publication does not extend its lifetime.
- Reject missing, future or too-old publication timestamps; HTML/error/redirect
  responses; malformed JSON; oversized responses; empty/missing USD coverage;
  duplicate, timezone-naive, wrong-week or ambiguous blocking events.
- Reject a regressed publication timestamp or changed content under the same
  publication timestamp. Store only safe diagnostic codes, not response bodies.
- Replace events, coverage and success metadata in one transaction. Read coverage
  and events in one statement to avoid mixing versions during a refresh.
- On failure retain the last good snapshot and its original freshness. It remains
  usable only until its original deadline. Then news becomes UNKNOWN and the
  deterministic preflight refuses approval without an LLM call.
- Backend rechecks news after reasoning as well. Automated provider configuration
  rejects `REQUIRE_VERIFIED_NEWS=false` at startup.
- ShowMyTrades coverage must match the requested rolling window: six hours
  before publication to seven days after. Window edges are trimmed for adjacent
  blackouts. Event UTC and epoch timestamps must agree; reported count must match;
  tentative/disputed schedules, missing confidence and invalid reschedules fail
  closed. Empty feeds are not evidence of a quiet week. A valid reschedule replaces
  the prior occurrence through the atomic snapshot update.
- Forex Factory coverage uses the publisher's Sunday-Saturday New York week, respecting DST.
  Adjacent weeks are not fetched. The 30-minute gaps at weekly edges deliberately
  remain UNKNOWN to avoid missing overlapping blackout windows across rollover.
- Manual calendar PUT returns HTTP 409 in automatic mode to prevent competing
  manual/automatic writers. Switch to manual mode before a manual override.

No system can guarantee the publisher's timestamps prove all event facts are
current. This gate detects known freshness/format/coverage failures, not every
possible upstream omission or incorrectly republished event.

## Verify and Monitor

Use the existing authenticated dashboard and Processing Status (`GET /status`).
`news_refresh` contains provider, enabled flag, last attempt, last successful
download, publisher timestamp, last error, next attempt and consecutive failures.
The next attempt is an earliest retry deadline, not a promise of successful data
or an always-on worker. `GET /context/news-calendar`
returns current ES/NQ status and `fresh_until`. Public `/health` intentionally
checks liveness, not news readiness. No extra public diagnostic endpoint is added.

Check that a publisher timestamp is present and recent, the snapshot covers now,
and current coverage is CLEAR or a justified BLACKOUT. UNKNOWN must never be
treated as permission to approve. The dashboard displays refresh failures and
the distinction between fetch time and source publication time.

TradingView alert observations still require a separate operator check. This
change does not automatically certify an alert is active or extend its expiry.

## Rollback

Set `NEWS_PROVIDER=manual`, keep `REQUIRE_VERIFIED_NEWS=true`, and redeploy.
Upload a freshly verified manual calendar with the existing authenticated
operator helper after the automatic worker is stopped. Never renew the date on
an old snapshot just to make it appear fresh. Do not revert to mock/unverified
news to bypass a production block. The webhook URL and alert need no change.

## Implementation Validation

On November 8, 2026, a read-only live feed probe parsed 37 USD events, including
23 HIGH after the conservative speech policy. Publisher timestamp was
`2026-11-08T17:42:17Z`; bounded weekly coverage ended `2026-11-15T04:30:00Z`.
This probe did not write production data or enable production automation.
These counts are observations, not permanent expectations or completeness proof.

Automated tests cover publisher freshness, failed refresh retention, cooldown
after restart, DST/week rollover, atomic rollback, HTTP failures, parsing failures,
live-mode opt-in lifecycle, approved/blackout/stale webhook decisions and UI output.
The replacement suite additionally covers provider isolation, timestamp agreement,
publication-clock independence, reschedules, uncertain events, the hard two-hour
stale limit, authenticated monitoring output and end-to-end stale/blackout refusal.
Tests use mock HTTP/provider responses; live source probes are separate.
Publisher HTTP errors retain a
safe `publisher_http_<status>` code without response bodies or URLs. The initial
legacy `HTTPStatusError` record cannot retrospectively identify its status code.
