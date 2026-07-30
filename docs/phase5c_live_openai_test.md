# Phase 5C Controlled Live OpenAI Test

Date: 2026-07-30

## Scope

A single local TradingView-style sample was submitted to the FastAPI backend.
TradingView, its active alert, and Pine were not modified.

- Backend: `http://127.0.0.1:8003`
- Endpoint: `POST /webhook/tradingview`
- Payload: `examples/pine_alert_payload_example.json`
- Provider configuration: `openai`
- Configured model: `gpt-4o-mini`
- News and Telegram context: mock adapters

The sender refreshed `bar_time` and `setup_id` before submission so the
checked-in sample remained schema-valid and unique.

## Provider Result

The backend selected and called the live OpenAI provider. The OpenAI request
failed with HTTP `429` (`RateLimitError`). No provider error message, request
headers, or credential value was printed or stored in this document.

Because the API did not return a model response, live OpenAI output schema
validation could not be confirmed in this run. The configured safe fallback
ran as designed:

- Stored model: `mock-llm-deterministic-openai-fallback`
- Fallback decision: `BUY`
- Confidence: `75`
- Risk/reward: `2.0`
- Deterministic validator: `APPROVED`
- Final action: `BUY`

The stored fallback output was independently checked against
`schemas/llm_trade_decision.schema.json`.

## Persistence and Dashboard

SQLite stored:

- the accepted setup
- parsed setup JSON
- enriched mock news and Telegram context
- fallback decision JSON
- deterministic validator result

`GET /decisions/latest` returned the new fallback-backed record. The local
dashboard loaded successfully and displayed the setup and decision.

## Follow-up

Before repeating the controlled live test, resolve the OpenAI account's
rate-limit or quota condition. Do not enable live TradingView-to-OpenAI
processing based on this run alone. Repeat the local sample test and require a
stored model equal to the configured OpenAI model rather than the fallback
identifier.

The sample sender timeout was increased to 60 seconds because the previous
10-second client timeout could expire while the backend was still completing
the configured OpenAI retry window.

## Safety

- No trades were placed.
- No broker was connected.
- Replay tools were not used.
- TradingView alerts were not created, deleted, or updated.
- Pine was not modified.
- `backend/.env` remained gitignored and uncommitted.
- No API key was printed, logged, documented, or committed.
