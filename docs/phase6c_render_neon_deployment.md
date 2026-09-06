# Phase 6C: Render and Neon Deployment

## Architecture

- Render Free runs the Dockerized FastAPI backend and provides HTTPS.
- Neon Free provides persistent PostgreSQL storage.
- UptimeRobot checks the public `/health` endpoint every five minutes.
- OpenAI remains selected through environment variables with deterministic mock fallback.
- TradingView continues using the existing local quick-tunnel alert until public validation and a separate cutover approval.

Render Free can stop after 15 minutes without inbound traffic and can restart at
any time. UptimeRobot reduces idle stops but does not provide an availability
guarantee. PostgreSQL is required because Render Free does not provide a
persistent filesystem and local SQLite data would be lost on a restart.

## Render Service

Create a Blueprint from the repository root. `render.yaml` configures one free
Docker web service with `/health` as its health check. Configure these secret
values in Render; never put their values in source control:

```dotenv
DATABASE_URL=<Neon pooled PostgreSQL connection string with SSL>
WEBHOOK_SECRET=<long random value>
DASHBOARD_USERNAME=<private username>
DASHBOARD_PASSWORD=<long random value>
OPENAI_API_KEY=<OpenAI API key>
```

The Blueprint configures the non-secret production values, including
`LLM_PROVIDER=openai` and `OPENAI_MODEL=gpt-4o-mini`. Render supplies `PORT`,
and the Docker image binds Uvicorn to `0.0.0.0`.

## Neon Database

Create a Neon Free project in a region near the Render service. Use the pooled
connection string with `sslmode=require` as Render's `DATABASE_URL`. The
backend normalizes `postgres://` and `postgresql://` URLs to SQLAlchemy's
psycopg 3 dialect. Tables are created during application startup.

## UptimeRobot

Create one HTTP monitor after Render is healthy:

```text
URL: https://<render-service>.onrender.com/health
Interval: 5 minutes
Expected response: HTTP 200
```

Do not monitor an authenticated dashboard or webhook URL. The health endpoint
contains no credentials.

## Validation Gate

Before changing TradingView:

1. Confirm public `/health` returns 200.
2. Confirm unauthenticated `/dashboard` returns 401.
3. Confirm authenticated `/dashboard` returns 200.
4. Send a unique sample payload to the secret-protected webhook.
5. Confirm `/decisions/latest` stores `gpt-4o-mini` or records the safe fallback.
6. Confirm the setup remains after a Render restart.
7. Confirm UptimeRobot reports the health monitor as up.
8. Obtain explicit approval to edit the existing TradingView alert in place.

The future webhook format is:

```text
https://<render-service>.onrender.com/webhooks/tradingview?secret=<redacted>
```

## Rollback

Keep the current local backend and Cloudflare quick tunnel operational until
Render and Neon pass every validation step. If the hosted path fails after a
later cutover, edit the single existing TradingView alert back to a verified
quick-tunnel URL. Do not create a duplicate alert.

This deployment remains decision support only. It does not place trades,
connect to a broker, or use replay trading.

## Deployment Result

Phase 6C was deployed and validated on September 6, 2026:

- Render Free is live at `https://<render-service>.onrender.com`.
- Neon PostgreSQL retained the test setup and decision across a Render restart.
- Public `GET /health` returned 200.
- The dashboard returned 401 without credentials and 200 with valid Basic Auth.
- A controlled Pine-style webhook was accepted through the public HTTPS URL.
- The stored decision used `gpt-4o-mini`, returned `BUY` with confidence 75,
  and passed deterministic validation.
- UptimeRobot monitor `803927270` checks `/health` every five minutes. The app
  supports both `GET` and `HEAD` health probes. The monitor reported `Up` after
  the first scheduled check against the corrected deployment. Its initial 405
  incident was caused by the previously missing `HEAD` handler and is resolved.
- After explicit approval, existing TradingView alert `5262922741` was edited
  in place to use the stable Render webhook. Exactly one active alert remains.

The completed alert cutover is documented in
`docs/phase6c_tradingview_render_cutover.md`.

Secrets and the full hosted URL are redacted. No secret was committed or
printed. No trades were placed, no broker was connected, and replay trading was
not used.
