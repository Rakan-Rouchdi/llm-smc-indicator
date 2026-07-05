# API Notes

Phase 3 exposes the local webhook-to-decision workflow using mock context and the mock LLM provider.

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
- enriches it with mock news and Telegram context
- calls the mock LLM provider
- validates the LLM decision deterministically
- stores the final validator result
- returns the final decision response

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

```http
GET /setups/{id_or_setup_id}
```

Returns one setup plus all stored decisions for that setup.

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
