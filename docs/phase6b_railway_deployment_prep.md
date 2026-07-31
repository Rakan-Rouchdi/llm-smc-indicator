# Phase 6B Railway Deployment Preparation

Date: 2026-07-31

## Status

The repository is prepared for a future Railway deployment. Phase 6B does not
create a Railway project, upload secrets, deploy code, stop the local quick
tunnel, or modify the TradingView alert.

Railway will build the root `Dockerfile` using `railway.toml`. The application
listens on Railway's injected `PORT`, exposes `/health` publicly, stores SQLite
on a mounted volume, and protects dashboard pages with HTTP Basic
authentication.

Railway references:

- <https://docs.railway.com/builds/dockerfiles>
- <https://docs.railway.com/config-as-code/reference>
- <https://docs.railway.com/deployments/healthchecks>
- <https://docs.railway.com/volumes>
- <https://docs.railway.com/networking/public-networking>

## Project Setup

1. Create an empty Railway project on the Hobby plan.
2. Add a service from this repository or use `railway up` from the project
   root.
3. Confirm Railway detects the root `Dockerfile` and `railway.toml`.
4. Keep one service replica while SQLite is in use.
5. Add a Railway volume to the backend service.
6. Generate a Railway public domain only after variables and the volume are
   configured.

Do not set a Railway service root directory to `backend`. The Docker build
needs the repository root so it can copy both `backend/` and `schemas/`.

## Required Variables

Configure these in Railway's service Variables panel. Values shown below are
names or placeholders, not credentials:

```dotenv
APP_ENV=production
DATABASE_URL=sqlite:////data/smc_llm.db
WEBHOOK_SECRET=<generate-a-long-random-value>
DASHBOARD_USERNAME=<private-dashboard-user>
DASHBOARD_PASSWORD=<generate-a-long-random-value>
LLM_PROVIDER=openai
OPENAI_API_KEY=<configure-in-Railway-only>
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20
LLM_MAX_RETRIES=2
```

Railway injects `PORT`; do not hardcode it. Mock mode remains available by
setting `LLM_PROVIDER=mock`. If live OpenAI is selected but unavailable or its
output is invalid, the deterministic mock fallback remains active.

Optional existing variables include confidence thresholds, setup age, news
blackout windows, notification settings, Telegram settings, and timezone. News
and Telegram remain mock adapters unless their integrations are configured.

## Persistent SQLite Volume

Attach one Railway volume to the backend service:

```text
Mount path: /data
Database URL: sqlite:////data/smc_llm.db
```

The four slashes in the SQLAlchemy URL are intentional: `/data/smc_llm.db` is
an absolute filesystem path. Enable Railway volume backups after deployment.
Services with volumes can have brief downtime during redeploys, and SQLite
must remain single-replica.

The existing local `sqlite:///./smc_llm.db` fallback remains unchanged for
development.

## Build and Start

Railway configuration uses:

```text
Builder: Dockerfile
Dockerfile: Dockerfile
Start command: uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port $PORT
Health check path: /health
Health check timeout: 60 seconds
```

The `.dockerignore` excludes local `.env` files, virtual environments,
databases, tests, and local-only artifacts from the image build context.

## Dashboard Authentication

The following HTML routes are protected together:

- `/`
- `/dashboard`
- `/dashboard/setups/{setup_identifier}`

When `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` are set, browsers receive an
HTTP Basic authentication challenge. In `APP_ENV=production`, absent or
partially configured credentials make dashboard routes return HTTP 503 rather
than exposing setup history or raw payloads.

In `development`, `dev`, `local`, or `test`, both values may be omitted to keep
the existing local dashboard workflow. If either credential is configured,
both are required and authentication is enforced in every environment.

`/health` remains public for Railway health checks. Dashboard credentials are
separate from `WEBHOOK_SECRET`.

## Stable URLs

After Railway generates a public domain:

```text
Health: https://<railway-service-domain>/health
Dashboard: https://<railway-service-domain>/dashboard
Webhook: https://<railway-service-domain>/webhooks/tradingview?secret=<redacted>
```

TradingView cannot set arbitrary authentication headers for this alert, so the
webhook continues using the query secret. Incoming JSON still passes schema,
Pydantic, LLM-output, and deterministic validation.

Do not update TradingView until the Railway health, authenticated dashboard,
sample webhook, SQLite persistence, live OpenAI response, and fallback path
have all been verified.

## Deployment Verification

For Phase 6C:

1. Deploy with the volume and variables configured.
2. Require HTTP 200 from public `/health`.
3. Require HTTP 401 from `/dashboard` without credentials and HTTP 200 with
   credentials.
4. Send a unique sample webhook using the Railway secret.
5. Confirm `/decisions/latest` and authenticated dashboard update.
6. Restart or redeploy once and confirm the SQLite record persists.
7. Confirm the stored model is `gpt-4o-mini`, or verify safe mock fallback if
   OpenAI fails.
8. Obtain explicit approval before editing the one existing TradingView alert.

## Rollback

Until the TradingView cutover is separately approved, the existing local
backend and Cloudflare quick tunnel remain the active path.

If Railway validation fails after a later cutover:

1. Start the local backend with the matching local `WEBHOOK_SECRET`.
2. Start a fresh quick tunnel.
3. Verify its public `/health` endpoint.
4. Edit the existing TradingView alert in place; do not create a duplicate.
5. Confirm exactly one matching active alert remains.

No trades, broker connections, replay tools, Pine changes, or TradingView alert
changes are part of this deployment preparation.
