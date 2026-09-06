# Phase 6D: Main Branch Deployment

Date: September 6, 2026

## Transition

GitHub pull request 1 merged `codex/phase6c-render-neon` into `main` at commit
`3b7abea`. The local workspace was fast-forwarded to the merged commit, and the
Render service deployment branch was changed from the feature branch to
`main`.

The branch change triggered a successful Render deployment from merge commit
`3b7abea`. The service URL, protected environment variables, Neon database,
UptimeRobot monitor, and TradingView webhook URL were not changed.

`render.yaml` now declares `branch: main` so the repository configuration
matches the live Render service and future Blueprint synchronization retains
the production branch.

## Verification

- Render deployment status: live
- Public `/health`: HTTP 200
- Unauthenticated `/dashboard`: HTTP 401
- Authenticated `/dashboard`: HTTP 200
- Neon setup and decision record persisted across deployment
- Latest stored model: `gpt-4o-mini`
- Latest stored decision: `BUY`
- Deterministic validator status: `APPROVED`
- Backend tests: 46 passed
- TradingView active matching alerts: exactly one
- TradingView alert ID: `5262922741`
- Pine JSON alert input: enabled
- Pine test webhook input: disabled

No alert was created, deleted, or duplicated during this transition. No trades
were placed, no broker was connected, replay trading was not used, and no
secret was printed or committed.
