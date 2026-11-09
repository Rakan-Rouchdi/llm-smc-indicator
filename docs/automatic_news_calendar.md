# Automatic Scheduled-News Coverage

## Status and Scope

Deployed and enabled on November 9, 2026, after PR #5 was merged. The first
Render-side fetch failed with `HTTPStatusError`; a controlled retry confirmed
`publisher_http_429` (rate limiting). No successful automatic refresh has yet
been verified. Production correctly reports ES/NQ UNKNOWN and blocks
approvals. This is a deployment blocker, not a successful feed cutover. See
`docs/timing_session_fixes_2026_11_09.md` for rollout evidence and limitations.

The source is the [Forex Factory calendar's Weekly Export](https://www.forexfactory.com/calendar),
which links to the public [JSON feed](https://nfs.faireconomy.media/ff_calendar_thisweek.json).
No API key, LLM browsing, local Codex automation or browser scraping is used.
Only scheduled USD events are mapped to ES/NQ. The provider's High impact events
are blocked. FOMC/Fed-labelled appearances are additionally elevated to HIGH,
matching the existing conservative manual policy. All HIGH events retain the
configured 30-minute-before/after blackout by default.

"Source-validated" means known HTTPS source, strict parsing, bounded current-week
coverage and publisher freshness checks. It does NOT mean each event is
independently corroborated against primary agencies. An incomplete but structurally
valid publisher feed cannot be detected reliably. No breaking-news, earnings,
global systemic-risk or gold coverage guarantee is implied. The feed has no
contractual SLA here; review provider licensing before customer redistribution.

## Enable After Deployment

Set these non-secret variables in Render after deploying the code:

```dotenv
NEWS_PROVIDER=forexfactory
REQUIRE_VERIFIED_NEWS=true
NEWS_MAX_AGE_HOURS=24
NEWS_REFRESH_INTERVAL_MINUTES=60
NEWS_FETCH_TIMEOUT_SECONDS=10
```

Keep all existing database, webhook, dashboard and OpenAI settings unchanged.
No new secret is required. The default provider remains mock for new local
installs. Production now uses `NEWS_PROVIDER=forexfactory` with strict coverage
required; failure never falls back to mock news or renews the manual snapshot.

The lifespan-managed thread checks on process startup and approximately hourly.
A durable cooldown avoids repeated fetches on rapid restarts. Use the existing
single Uvicorn worker/one Render replica; this is not a distributed scheduler.
The new `calendar_refresh` table is additive and created by existing startup
metadata initialization on SQLite/PostgreSQL. Existing tables need no ALTER.

The thread runs only while the service process runs. [Render Free can spin down](https://render.com/docs/free#spinning-down-on-idle);
it is not an always-on scheduler. After wake-up/restart, stale data remains blocked
until a valid refresh succeeds. Uptime checks are not an availability guarantee.
For reliable unattended use, move to always-on hosting or a separately scheduled
authenticated ingestion service; do not relax the stale-data rule.

## Fail-Closed Rules

- Freshness uses HTTP `Last-Modified`, not the time of a successful download.
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
- Coverage uses the publisher's Sunday-Saturday New York week, respecting DST.
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
download, publisher timestamp and last error. `GET /context/news-calendar`
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
The original implementation suite had 153 passing tests. The November 9 timing
and deployment fixes bring the suite to 167 passed, zero failed, with one existing
Starlette/httpx deprecation warning. Tests use mock HTTP/provider responses;
live source probes are separate. Production enablement is verified, but a
successful hosted refresh is not. Subsequent publisher HTTP errors now retain a
safe `publisher_http_<status>` code without response bodies or URLs. The initial
legacy `HTTPStatusError` record cannot retrospectively identify its status code.
