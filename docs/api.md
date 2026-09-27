# API Notes

The backend stores alert receipts immediately, then processes them using the configured LLM provider. News and Telegram context remain mocked.

## Health

```http
GET /health
```

Response:

```json
{"status": "ok"}
```

## TradingView Webhook

```http
POST /webhook/tradingview
POST /webhooks/tradingview
```

Authentication uses `X-Webhook-Secret` or `?secret=`.

The request body must match `schemas/setup_alert.schema.json`. The backend then:

- stores the raw payload
- parses the setup with Pydantic
- commits a durable decision job alongside the setup
- returns HTTP 202 with `{"status":"accepted","setup_id":"...","duplicate":false}`

The background worker enriches context, calls the configured provider, runs the deterministic validator and stores the decision. A repeated setup ID returns HTTP 200 with `status: duplicate` and does not schedule another LLM call. Query `/setups/{setup_id}` for processing state, job attempts/errors and decisions. A receipt acknowledgement is not a completed decision.

Jobs survive restarts, recover expired worker leases and retry unexpected failures up to three attempts. This deployment runs one Uvicorn process with one worker thread. Idle recovery scans are hourly; a new receipt wakes the worker immediately, and pending retries/leases schedule earlier scans.

Sample:

```bash
curl -X POST http://localhost:8000/webhook/tradingview \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Secret: change-me' \
  --data @examples/tradingview_webhook_example.json
```

## Setup History

```http
GET /setups
```

Returns recent setup records with raw payload, parsed setup, and enriched context.

All setup, decision, outcome and `/status` routes require the same Basic Auth as the dashboard. Local development without configured dashboard credentials retains its existing unauthenticated behavior. Webhooks use only `WEBHOOK_SECRET`; `/health` stays public.

```http
GET /setups/{id_or_setup_id}
```

Returns one setup plus all stored decisions for that setup.

## Processing Status

`GET /status` checks database connectivity and reports worker liveness and job counts. `/health` is only process liveness; it does not prove webhook delivery or OpenAI availability.

Pine v13 emits the bar opening time. Freshness is measured from the estimated close for supported minute resolutions 5, 15, 60 and 240. An optional `diagnostics.bar_close_time` gives an exact close (including shortened session bars). Legacy shortened bars whose calculated close is still in the future are conservatively rejected rather than treated as fresh. Pine trading rules and the existing alert snapshot are unchanged.

## Latest Decision

```http
GET /decisions/latest
```

Returns the most recent stored decision, including:

- raw LLM JSON
- validator result JSON
- final action
- confidence
- entry, SL, TP1, RR
- validation rejection reason

## Outcome Placeholder

```http
POST /setups/{setup_id}/outcome
```

Body:

```json
{
  "outcome": "UNKNOWN",
  "notes": "Manual placeholder outcome."
}
```

Supported outcome values:

- `WIN`
- `LOSS`
- `EXPIRED`
- `UNKNOWN`
