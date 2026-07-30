# SMC LLM Trade Setup Validator

Local MVP for an LLM-powered Smart Money Concepts TradingView workflow.

The MVP is decision support only. It does not place trades, connect to brokers, use replay trading, or create TradingView alerts automatically.

## Current Scope

- Pine indicator implemented and validated through TradingView MCP for ES/NQ on 5m, 15m, 1h, and 4h.
- FastAPI backend receives TradingView-style setup alerts.
- Incoming webhook JSON is validated against `schemas/setup_alert.schema.json`.
- Pydantic models parse setup alerts and LLM decisions.
- Mock news and Telegram context are added.
- Mock deterministic LLM provider returns strict JSON.
- Deterministic validator approves or converts decisions to `NO_TRADE`.
- SQLite stores setups, context, decisions, validator results, and outcome placeholders.
- Local dashboard displays latest setup, history, context, decision, validation, and raw payloads.

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

Phase 3 uses `LLM_PROVIDER=mock` by default. OpenAI-compatible live routing is intentionally deferred.

`.env`, `backend/.env`, SQLite database files, and local virtualenvs are gitignored.

## Validation Docs

- Phase 2B TradingView validation: `docs/phase2b_validation.md`
- Phase 2C 4h validation: `docs/phase2c_4h_validation.md`
- Phase 4A TradingView alert setup: `docs/tradingview_alert_setup.md`
- Live MVP restart guide: `docs/restart_live_mvp.md`
- Live MVP monitoring: `docs/live_mvp_monitoring.md`
- Stable deployment options: `docs/stable_deployment_options.md`

Screenshots remain in:

```text
/Users/rakanrouchdi/tradingview-mcp-jackson/screenshots/
```
