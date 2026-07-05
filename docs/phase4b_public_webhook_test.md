# Phase 4B Public Webhook Test

Date: 2026-07-05 UTC

Scope: prove that a public HTTPS webhook path can reach the local FastAPI backend and complete the existing mock LLM workflow. No TradingView alert was created, `alert_create` was not used, no trades were placed, no replay trade tools were used, no broker connection was made, and the mock LLM remained active.

## Runtime Setup

- Backend port used: `8003`
- Backend bind address: `127.0.0.1:8003`
- Temporary secret handling: generated at runtime, stored only in `/tmp/llm_smc_phase4b_secret` during the test, then removed after validation
- Tunnel tool used: `cloudflared`
- Tunnel version: `2026.6.1`
- Tunnel type: Cloudflare quick tunnel
- Public URL, redacted: `https://textile-variable-...-carey.trycloudflare.com`

## Webhook Request

- Webhook path used: `/webhooks/tradingview?secret=<REDACTED>`
- Public webhook URL format:

```text
https://textile-variable-...-carey.trycloudflare.com/webhooks/tradingview?secret=<REDACTED>
```

- Test payload file used:

```text
examples/pine_alert_payload_example.json
```

## Backend Response Summary

- HTTP status: `200`
- Response status: `processed`
- Duplicate: `false`
- Stored setup id: `CME_MINI_DL:ES1!_5_1783334400000_424242`
- Symbol: `CME_MINI_DL:ES1!`
- Timeframe: `5`
- Direction: `BULLISH`
- Rule score: `75`
- Validator status: `APPROVED`
- Final action: `BUY`

## SQLite Storage Verification

SQLite row confirmed in `setup_alerts`:

```text
id=2
setup_id=CME_MINI_DL:ES1!_5_1783334400000_424242
symbol=CME_MINI_DL:ES1!
timeframe=5
status=PROCESSED
```

## Latest Decision Summary

`GET /decisions/latest` returned the new mock LLM decision:

- Model: `mock-llm-deterministic`
- Prompt version: `smc_llm_v1`
- Raw LLM action: `BUY`
- Final action: `BUY`
- Confidence: `75`
- Entry: `6721.25`
- Stop loss: `6714.75`
- Take profit 1: `6734.25`
- Risk/reward: `2.0`
- Validator status: `APPROVED`
- Rejection reason: none
- Headline driver: mock news context

## Dashboard Verification

Dashboard verified locally and through the public tunnel.

Observed rendered dashboard fields:

- Latest symbol: `CME_MINI_DL:ES1!`
- Latest setup id: `CME_MINI_DL:ES1!_5_1783334400000_424242`
- Latest decision: `BUY`
- Validation status: `APPROVED`
- Mock news context rendered

## Notes

- Mock LLM was used.
- Mock news context was used.
- Mock Telegram context was used.
- No OpenAI credentials were read or used.
- No TradingView alert was created.
- No `alert_create` call was made.
- The public tunnel was used only for this webhook reachability test.
- The temporary tunnel process and local backend process were stopped after validation.
