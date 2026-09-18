# TradingView Alert Replacement: September 18, 2026

## Outcome

- Replaced the stale NQ 4h alert after explicit user approval. Old alert `5262922741` was paused and deleted.
- Exactly one alert remains: `5647010108`, active, named `SMC LLM Candidate Detector webhook`.
- Condition: `SMC LLM Candidate Detector -> Any alert() function call` on NQ 4h. It uses saved Pine version 13.0, with JSON alerts enabled and the test webhook input disabled. The message comes from the script's `alert()` call; no static JSON is pasted into the alert.
- The alert targets the protected Render `/webhooks/tradingview` endpoint. Its HTTPS host and query secret are intentionally omitted here.
- The alert expires on **October 18, 2026 at 17:48:44 UTC**. The available open-ended option required an account upgrade, so the expiration must be renewed before that date.

## Validation and security

- Pine version 13.0 compiled with zero errors and zero warnings. The higher-timeframe bias now uses the last completed higher-timeframe candle to make historical diagnostics and realtime alert evaluation consistent.
- Render `/health` returned HTTP 200. A deliberately invalid webhook body authenticated using the replacement secret and returned HTTP 422 for schema validation, confirming that the current endpoint and secret agree without storing a setup or calling the LLM.
- During inspection, a tool output inadvertently displayed the previous webhook secret. It was rotated in Render and the replacement alert uses the new secret. Neither secret is included in this document or committed files. The exposed value should not be reused anywhere else.
- No natural TradingView candidate alert had arrived by the end of this replacement. The hosted latest decision was still the September 6 controlled test, not evidence of a new live alert delivery.
- No trades were placed, replay or broker tools were not used, and no OpenAI credential was inspected or changed.

## Operating note

An active alert does not guarantee a candidate on every bar. Keep the Render service and TradingView alert active, review TradingView delivery logs and the dashboard for the first natural candidate, and renew the alert before its expiration. Do not create a second alert to renew it; replace the existing one so only one is active.
