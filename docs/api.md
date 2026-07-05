# API Notes

Phase 1 exposes a minimal FastAPI skeleton.

## Health

```http
GET /health
```

Response:

```json
{"status": "ok"}
```

## TradingView Webhook

Both paths are reserved for the same TradingView payload contract:

```http
POST /webhook/tradingview
POST /webhooks/tradingview
```

Authentication uses `X-Webhook-Secret` or `?secret=`.

Phase 1 validates and stores accepted setup alerts, then processes them with the mock LLM provider.
