# Project Rules

Follow `docs/PRD.md` as the source of truth for product behavior, schemas, safety rules, and acceptance criteria.

Hard constraints:

- Never place trades.
- Never connect to a broker.
- Never use `replay_trade`.
- Never create TradingView alerts without explicit user confirmation.
- Never put secrets in Pine Script, source code, tests, or committed files.
- Use mock LLM, news, and Telegram providers unless credentials are configured.
- Treat all TradingView webhooks as untrusted input and validate them before storage or processing.

MVP scope:

- This project is for analysis, signal generation, dashboarding, validation, and logging only.
- Pine emits provisional chart setup payloads. Final LLM decisions are shown by the backend/dashboard.
- No automatic round-trip plotting of LLM decisions back into TradingView is included in the MVP.
