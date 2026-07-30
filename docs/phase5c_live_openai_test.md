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

## Initial Follow-up

Before repeating the controlled live test, resolve the OpenAI account's
rate-limit or quota condition. Do not enable live TradingView-to-OpenAI
processing based on this run alone. Repeat the local sample test and require a
stored model equal to the configured OpenAI model rather than the fallback
identifier.

The sample sender timeout was increased to 60 seconds because the previous
10-second client timeout could expire while the backend was still completing
the configured OpenAI retry window.

## Retry After Adding API Credits

The controlled test was repeated after API credits were added.

- Backend provider configuration: `openai`
- Configured model: `gpt-4o-mini`
- Credential configured: yes, checked as a boolean only
- Backend health: passed
- Controlled payload: `examples/pine_alert_payload_example.json`
- Endpoint: `POST /webhook/tradingview`
- Live OpenAI provider selected and called: yes
- Live OpenAI request succeeded: no
- Sanitized API result: HTTP `429` (`RateLimitError`)
- Stored model: `mock-llm-deterministic-openai-fallback`
- Fallback decision: `BUY`
- Confidence: `75`
- Risk/reward: `2.0`
- Deterministic validator: `APPROVED`
- Dashboard: passed and displayed the latest fallback-backed decision

A 60-second propagation window was allowed before one final controlled webhook
attempt. That attempt still received HTTP `429` and used the mock fallback.
No further retries were made.

This retry did not meet the success criterion. Before another attempt, confirm
that billing is active for the same OpenAI organization/project associated with
the configured key and that the project has a usable spend limit. A successful
retry must store `model: gpt-4o-mini`.

## Successful Retry After Credits Became Active

The controlled test was repeated again after the API credits became active.
This run met all Phase 5C success criteria.

- Backend provider configuration: `openai`
- Model requested and stored: `gpt-4o-mini`
- Controlled payload: `examples/pine_alert_payload_example.json`
- Endpoint: `POST /webhook/tradingview`
- OpenAI provider succeeded: yes
- OpenAI decision schema: valid
- Pydantic decision validation: passed
- OpenAI action: `BUY`
- Final deterministic action: `BUY`
- Confidence: `75`
- Risk/reward: `2.0`
- Deterministic validator: `APPROVED`
- Mock fallback used: no
- SQLite setup status: `PROCESSED`
- Parsed payload, enriched context, OpenAI decision, and validator result:
  stored
- `GET /decisions/latest`: returned `model: gpt-4o-mini`
- Dashboard: displayed the setup, model, action, confidence, and validator
  status

The dashboard now renders the stored provider model in its latest-decision
panel, making OpenAI provenance visible without inspecting SQLite.

No trades were placed. TradingView alerts and Pine were not modified. The API
key remained only in the gitignored `backend/.env` file and was not printed,
documented, or committed.

## Safety

- No trades were placed.
- No broker was connected.
- Replay tools were not used.
- TradingView alerts were not created, deleted, or updated.
- Pine was not modified.
- `backend/.env` remained gitignored and uncommitted.
- No API key was printed, logged, documented, or committed.
