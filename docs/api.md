# API Notes

The backend stores alert receipts immediately, then processes them using the configured LLM provider. News supports verified manual and automatic calendars; Telegram sentiment context remains mocked. Final outgoing Telegram notifications are a separate opt-in feature.

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

Returns one setup plus all stored decisions, processing job and `delivery`
evidence for that setup. Evidence includes candle-close-to-receipt,
receipt-to-processing, provider/preflight duration, receipt-to-decision-record,
feed status, detector revision and final notification state. Missing timings
are `null`, not zero. Negative close-to-receipt values are flagged as
`CLOCK_OR_PAYLOAD_ERROR`. Decision timestamps precede commit; these values do
not measure the public HTTP acknowledgement or delivery to a phone.

## Processing Status

`GET /status` checks database connectivity and reports worker liveness and job counts. `/health` is only process liveness; it does not prove webhook delivery or OpenAI availability.

Pine emits the bar opening time and revision 19 includes exact
`diagnostics.bar_close_time` (including shortened session bars). Legacy payloads
without the close use estimated minute-resolution closes; future calculated
closes are conservatively rejected. Exact metadata does not remove delayed
market feeds or pivot/confirmed-bar detection latency.

## Delivery And Evaluation

`GET /notifications` reports outbox states. `SENT` means the destination returned
success, not that the user read a message. `UNKNOWN` requires reconciliation,
not an automatic retry. All notification and evaluation routes require
dashboard authentication in production.

`GET /evaluation` reviews the newest 500 setups, using only the newest decision
and outcome per setup. The eligible cohort requires `strict_v1`,
`timing_sessions_v2`, an approved BUY/SELL and an OpenAI-requested non-fallback
decision. Delivery tests, legacy revisions, pending/failed, rejected and
non-live decisions have separate exclusion counts. Manual outcome counts are
returned with `accuracy_status=NOT_ESTABLISHED`; no win rate is inferred.

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
