# SMC LLM Trade Setup Validator

Local MVP for an LLM-powered Smart Money Concepts TradingView workflow.

The MVP is decision support only. It does not place trades, connect to brokers, use replay trading, or create TradingView alerts automatically.

## Current Scope

- Pine indicator implemented and validated through TradingView MCP for ES/NQ on 5m, 15m, 1h, and 4h.
- FastAPI commits TradingView alert receipts and durable decision jobs, returning HTTP 202 before LLM processing.
- Incoming webhook JSON is validated against `schemas/setup_alert.schema.json`.
- Pydantic models parse setup alerts and LLM decisions.
- Verified manual news-calendar context and opt-in automatic scheduled-calendar refresh are available; Telegram remains mock.
- Configurable OpenAI provider with deterministic mock fallback returns strict JSON.
- Deterministic validator approves or converts decisions to `NO_TRADE`.
- SQLite locally and PostgreSQL on Neon store setups, jobs, context, decisions, validator results, and outcome placeholders.
- Local dashboard displays latest setup, history, context, decision, validation, and raw payloads.

## Strict Policy and Operations Update

The November 2026 implementation uses `strict_v1` Pine facts, exact candle-close
timestamps, a 100-point confirmation rubric, and mirrored backend eligibility
checks. Legacy snapshots remain stored but cannot receive strict approval.
Unknown/stale news coverage blocks approval by default. This is intentional:
an empty mock calendar is not evidence that no market event exists.

Read [implementation and rollout notes](docs/strict_policy_rollout.md) before
deploying. They include manual calendar ingestion, alert-expiry observations,
authenticated hosted checks, notification setup, and the exact proposed alert
replacement. The updated chart does not update an existing alert snapshot.

`NEWS_PROVIDER=manual` and `REQUIRE_VERIFIED_NEWS=true` are the live configuration.
For isolated mock exercises only, use `NEWS_PROVIDER=mock` and explicitly set
`REQUIRE_VERIFIED_NEWS=false`. Keep `ENABLE_NOTIFICATIONS=false` during tests.
OpenAI failures are recorded with fallback provenance and held as `NO_TRADE`.
No mock/fallback, delivery-test, rejected, or expired decision is pushed as a
live final notification.

## Webhook Reliability

TradingView cancels requests that take longer than three seconds. Webhooks now return a receipt acknowledgement, not the LLM result. The in-process worker consumes persisted jobs and records the result separately. Check the authenticated `/setups/{setup_id}`, `/decisions/latest`, `/status`, and `/dashboard` routes after receipt. Dashboard credentials also protect data APIs and outcome updates; `/health` remains public and checks process liveness only.

Pine's `bar_time` is the candle opening time. The backend measures setup age from its close for the supported minute resolutions. The September 2026 incident and remaining free-hosting limitations are documented in `docs/webhook_delivery_audit_2026_09_27.md`. A green uptime check alone does not establish working alert delivery.

## Run Backend Locally

```bash
export WEBHOOK_SECRET="<local-secret>"
scripts/start_backend.sh
```

Health check:

```bash
scripts/check_backend_health.sh
```

Dashboard:

```text
http://localhost:8003/dashboard
```

The root route `/` also opens the dashboard.

For a public deployment, set `APP_ENV=production`, `DASHBOARD_USERNAME`, and
`DASHBOARD_PASSWORD`. Production dashboard routes fail closed when credentials
are absent or incomplete. `/health` remains public.

## Send A Sample Webhook

From the project root, with the backend running:

```bash
scripts/send_sample_webhook.sh
```

Equivalent curl:

```bash
curl -X POST http://localhost:8003/webhook/tradingview \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  --data @examples/tradingview_webhook_example.json
```

The alias path also works:

```text
POST /webhooks/tradingview
```

## API Routes

- `GET /health`
- `GET /status` (authenticated operations, alert observations, latency, queue)
- `GET /notifications` (authenticated notification delivery status)
- `GET /context/news-calendar` (authenticated calendar coverage)
- `PUT /context/news-calendar` (authenticated complete verified snapshot)
- `PUT /monitoring/alert` (authenticated observation only, not alert creation)
- `GET /setups`
- `GET /setups/{id_or_setup_id}`
- `GET /decisions/latest`
- `POST /webhook/tradingview`
- `POST /webhooks/tradingview`
- `POST /setups/{setup_id}/outcome`

Outcome status values are `WIN`, `LOSS`, `EXPIRED`, and `UNKNOWN`.

## Run Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Environment

Copy `backend/.env.example` to `backend/.env` for local overrides.

`LLM_PROVIDER=mock` remains the default. Phase 5B adds optional OpenAI routing
with deterministic mock fallback.

`.env`, `backend/.env`, SQLite database files, and local virtualenvs are gitignored.

## Optional OpenAI Provider

Mock mode remains the safe default. To prepare live OpenAI manually, copy the
example configuration and edit the gitignored file locally:

```bash
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

Set these values in `backend/.env` without committing or sharing the key:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=<add manually>
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20
LLM_MAX_RETRIES=2
```

If the key is absent or an OpenAI request/output fails, the provider fallback
remains available, but an OpenAI-requested workflow holds that fallback as
`NO_TRADE` for human review. It never pushes a mock BUY/SELL as a live decision.
The LLM output must pass JSON Schema, Pydantic, and deterministic trade validation.

See `docs/live_openai_integration.md` for the controlled enablement and rollback
procedure.

## Railway Deployment Preparation

The repository includes a root `Dockerfile` and `railway.toml`. Railway should
build from the repository root and start the backend with:

```text
uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port $PORT
```

Attach one Railway volume at `/data` and configure:

```dotenv
APP_ENV=production
DATABASE_URL=sqlite:////data/smc_llm.db
WEBHOOK_SECRET=<private-value>
DASHBOARD_USERNAME=<private-value>
DASHBOARD_PASSWORD=<private-value>
LLM_PROVIDER=openai
OPENAI_API_KEY=<private-value>
OPENAI_MODEL=gpt-4o-mini
```

Railway injects `PORT`. Keep one service replica while using SQLite. Do not
place any credentials in `railway.toml`, the Dockerfile, source code, or Git.

The future TradingView URL will be:

```text
https://<railway-service-domain>/webhooks/tradingview?secret=<redacted>
```

Deployment and cutover verification are documented in
`docs/phase6b_railway_deployment_prep.md`. Phase 6B does not deploy or modify
the existing TradingView alert.

## Render Free and Neon Deployment

Phase 6C uses `render.yaml` to deploy the Dockerized FastAPI service to Render
Free and uses Neon PostgreSQL for persistent storage. Local development remains
on SQLite. Managed `postgres://` and `postgresql://` URLs are automatically
configured for the bundled psycopg 3 driver.

Render must receive `DATABASE_URL`, `WEBHOOK_SECRET`, dashboard credentials,
and `OPENAI_API_KEY` through its secret environment settings. UptimeRobot can
monitor the public `/health` route every five minutes. It does not replace
persistent storage or provide a production availability guarantee.

See `docs/phase6c_render_neon_deployment.md` for setup, validation, and rollback.
The existing TradingView alert has been cut over in place to the stable Render
webhook; see `docs/phase6c_tradingview_render_cutover.md`.

## Automatic Calendar and Closed-Market Testing

The `NEWS_PROVIDER=showmytrades` worker refreshes a free, keyless scheduled USD
calendar every 15 minutes. Keep `REQUIRE_VERIFIED_NEWS=true` and
`NEWS_MAX_AGE_HOURS=2`. The adapter blocks medium/high events and Fed appearances.
Refresh failures never renew the last good snapshot;
stale/missing coverage produces NO_TRADE. This is source-validated scheduled
calendar coverage, not independent fact-checking or a breaking-news feed.

Deployment, source limitations, refresh diagnostics and rollback:
[Automatic news calendar](docs/automatic_news_calendar.md). Local defaults remain
mock; Render Blueprint configuration enables the automatic provider. Forex Factory
remains available but its Render requests were still rate-limited on November 10.

An isolated local dashboard preview works with the market closed:

```bash
backend/.venv/bin/python backend/scripts/preview_mvp.py --port 8012 --scenario approved
```

Open `http://127.0.0.1:8012/dashboard`. History includes approved, blackout, stale
and unsupported-gold fixtures; `--scenario` chooses which appears latest.
It uses disposable SQLite, mock reasoning, no `.env`, no outbound notifications
and no TradingView alert. Stop with Ctrl-C. Never tunnel this unauthenticated
loopback-only preview. See [closed-market testing](docs/closed_market_testing.md).

## Validation Docs

- Phase 2B TradingView validation: `docs/phase2b_validation.md`
- Phase 2C 4h validation: `docs/phase2c_4h_validation.md`
- Phase 4A TradingView alert setup: `docs/tradingview_alert_setup.md`
- Live MVP restart guide: `docs/restart_live_mvp.md`
- Live MVP monitoring: `docs/live_mvp_monitoring.md`
- Stable deployment options: `docs/stable_deployment_options.md`
- Railway deployment preparation: `docs/phase6b_railway_deployment_prep.md`
- Render and Neon deployment: `docs/phase6c_render_neon_deployment.md`
- TradingView Render cutover: `docs/phase6c_tradingview_render_cutover.md`
- Main branch deployment transition: `docs/phase6d_main_branch_deployment.md`
- Live OpenAI integration: `docs/live_openai_integration.md`

Screenshots remain in:

```text
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/
```
